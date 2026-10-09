from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

REPORT_TEMPLATE_VERSION = "2026.10.1"
REPORT_FORMATS = ("json", "html", "pdf")
DECISION_LABELS = {"approved": "批准", "rejected": "驳回", "changes_requested": "要求修改"}
RISK_LABELS = {"low": "低", "medium": "中", "high": "高", "critical": "严重"}
FONT_PATH = Path(__file__).parent / "assets" / "NotoSansSC-Regular.ttf"
FONT_RESOURCE_SHA256 = "e3b799e4230233500ff152d1cc81ade6c64acb34958c90cd6b6e02927a2923a9"
FONT_RESOURCE = {
    "name": "Noto Sans SC Regular",
    "license": "SIL Open Font License 1.1",
    "sha256": FONT_RESOURCE_SHA256,
}
NOTICE = "SYNTHETIC DEMO DATA ONLY / 演示仅使用虚构数据"
ATTRIBUTION = "基于 Langflow / Built on Langflow"


class ReportValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        self.retryable = False
        super().__init__(detail)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Hash a fixed whitelist payload. Callers exclude mutable execution fields first."""
    value = {key: item for key, item in payload.items() if key != "snapshot_hash"}
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def validate_decision_snapshot(payload: Mapping[str, Any], *, require_bound: bool = True) -> None:
    if payload.get("decision") not in DECISION_LABELS:
        raise ReportValidationError("decision_required", "A recorded human decision is required")
    reason = str(payload.get("decision_reason", payload.get("reason", ""))).strip()
    if not 8 <= len(reason) <= 1000:
        raise ReportValidationError(
            "invalid_decision_reason", "Decision reason must have 8 to 1000 characters"
        )
    score = payload.get("risk_score", payload.get("rule_score"))
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ReportValidationError("assessment_required", "A complete rule assessment is required")
    if payload.get("risk_level") not in RISK_LABELS:
        raise ReportValidationError("assessment_required", "Risk level is missing or unsupported")
    if not isinstance(payload.get("findings", []), list) or any(
        not isinstance(finding, dict) for finding in payload.get("findings", [])
    ):
        raise ReportValidationError(
            "assessment_required", "Rule findings must be structured records"
        )
    if not require_bound:
        return
    expected_level = (
        "critical" if score >= 75 else "high" if score >= 50 else "medium" if score >= 25 else "low"
    )
    if payload["risk_level"] != expected_level:
        raise ReportValidationError("assessment_required", "Risk score and level do not match")
    for field in (
        "case_id",
        "document_version_id",
        "assessment_id",
        "decision_id",
        "ruleset_version",
        "redaction_policy_version",
        "generated_at",
    ):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ReportValidationError(
                "snapshot_incomplete", f"Decision snapshot requires {field}"
            )
    for field in ("ruleset_hash", "redaction_policy_hash", "snapshot_hash"):
        if not _valid_sha256(payload.get(field)):
            raise ReportValidationError(
                "snapshot_incomplete", f"Decision snapshot requires {field}"
            )
    document_hash = payload.get("document_hash", payload.get("source_sha256"))
    if not _valid_sha256(document_hash):
        raise ReportValidationError("snapshot_incomplete", "Source document hash is required")
    if payload.get("source_kind") not in {"seed_demo", "uploaded_demo"}:
        raise ReportValidationError(
            "snapshot_incomplete", "Synthetic source classification is required"
        )
    if payload.get("hash_kind") not in {"synthetic_text", "source_bytes_sha256"}:
        raise ReportValidationError("snapshot_incomplete", "Document hash kind is required")
    reviewer = payload.get("decided_by", payload.get("reviewer"))
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReportValidationError("snapshot_incomplete", "A recorded reviewer is required")
    decided_at = payload.get("decided_at", payload.get("recorded_at"))
    for value in (decided_at, payload["generated_at"]):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Timezone is required")
        except ValueError as exc:
            raise ReportValidationError(
                "snapshot_incomplete", "Recorded times need ISO-8601 timezones"
            ) from exc
    if canonical_hash(payload) != payload["snapshot_hash"]:
        raise ReportValidationError(
            "snapshot_hash_mismatch", "Decision snapshot hash does not match"
        )


@lru_cache(maxsize=4)
def _font_resource(path: str) -> dict[str, str]:
    resource = Path(path)
    if not resource.is_file():
        raise ReportValidationError(
            "font_unavailable", "The configured Chinese report font is missing"
        )
    if hashlib.sha256(resource.read_bytes()).hexdigest() != FONT_RESOURCE_SHA256:
        raise ReportValidationError(
            "font_hash_mismatch", "Chinese report font differs from the pinned OFL resource"
        )
    return dict(FONT_RESOURCE)


def _font_path() -> str:
    return os.getenv("REVIEW_REPORT_FONT", str(FONT_PATH))


def report_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """One common format-independent representation; never mutates a decision snapshot."""
    validate_decision_snapshot(payload, require_bound=bool(payload.get("snapshot_hash")))
    result = dict(payload)
    result["risk_score"] = payload.get("risk_score", payload.get("rule_score"))
    result["document_hash"] = payload.get("document_hash", payload.get("source_sha256"))
    result["decision_reason"] = str(
        payload.get("decision_reason", payload.get("reason", ""))
    ).strip()
    result["decided_by"] = payload.get("decided_by", payload.get("reviewer"))
    result["decided_at"] = payload.get("decided_at", payload.get("recorded_at"))
    result["generated_at"] = payload.get("generated_at") or result["decided_at"] or "unknown"
    result["data_classification"] = "SYNTHETIC_DEMO_ONLY"
    result["workflow_engine"] = "Langflow"
    result["attribution"] = ATTRIBUTION
    result["synthetic_notice"] = NOTICE
    result["report_template_version"] = REPORT_TEMPLATE_VERSION
    result["font_resource"] = dict(FONT_RESOURCE)
    result["report_title"] = (
        "本次修订意见报告" if payload["decision"] == "changes_requested" else "文档审查决策报告"
    )
    result.setdefault("source_kind", "seed_demo")
    result.setdefault("hash_kind", "synthetic_text")
    result.setdefault("findings", [])
    result.setdefault("audit_events", [])
    return result


def _safe(value: object) -> str:
    return html.escape("unknown" if value is None else str(value))


def _meta_rows(payload: Mapping[str, Any]) -> list[tuple[str, object]]:
    return [
        ("案件", payload.get("title")),
        ("案件 ID", payload.get("case_id")),
        ("文档版本", payload.get("document_version_id")),
        ("评估 ID", payload.get("assessment_id")),
        ("决定 ID", payload.get("decision_id")),
        ("来源", payload.get("source_kind")),
        ("文档哈希类型", payload.get("hash_kind")),
        ("文档 SHA-256", payload.get("document_hash")),
        ("快照 SHA-256", payload.get("snapshot_hash")),
        ("规则版本", payload.get("ruleset_version")),
        ("规则 SHA-256", payload.get("ruleset_hash")),
        ("脱敏策略版本", payload.get("redaction_policy_version")),
        ("脱敏策略 SHA-256", payload.get("redaction_policy_hash")),
        ("生成时间", payload.get("generated_at")),
        ("报告模板", payload["report_template_version"]),
    ]


def _audit_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = payload.get("audit_events") or []
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise ReportValidationError("invalid_audit", "Audit events must be structured records")
    return events


def _audit_cutoff(payload: Mapping[str, Any]) -> object:
    return payload.get(
        "audit_through_id", payload.get("audit_cutoff", payload.get("audit_cutoff_id", "unknown"))
    )


def build_html_report(payload: dict[str, Any]) -> str:
    report = report_payload(payload)
    metadata = "".join(
        f"<dt>{_safe(label)}</dt><dd>{_safe(value)}</dd>" for label, value in _meta_rows(report)
    )
    findings = "".join(
        f"<article><h3>{_safe(finding.get('rule_id'))} · {_safe(finding.get('title'))}</h3>"
        f"<p>等级：{_safe(finding.get('severity'))}；定位：{_safe(finding.get('locator'))} "
        f"[{_safe(finding.get('start'))}:{_safe(finding.get('end'))}]</p>"
        f"<blockquote>{_safe(finding.get('evidence'))}</blockquote>"
        f"<p>建议：{_safe(finding.get('recommendation'))}</p></article>"
        for finding in report["findings"]
    )
    audit = "".join(
        f"<li>{_safe(event.get('occurred_at', event.get('timestamp')))} "
        f"· {_safe(event.get('event_type'))} · {_safe(event.get('actor'))} "
        f"· {_safe(event.get('detail'))}</li>"
        for event in _audit_rows(report)
    )
    full_snapshot = _safe(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{_safe(report["report_title"])}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:Arial,"Noto Sans SC",sans-serif;color:#161616;margin:32px auto;
max-width:960px;padding:0 24px;line-height:1.65;overflow-wrap:anywhere}}
h1{{font-size:28px}}h2{{font-size:20px;margin-top:28px}}
.notice{{padding:12px;background:#edf5ff;border-left:4px solid #0f62fe}}
dl{{display:grid;grid-template-columns:150px 1fr;gap:8px}}dt{{color:#525252}}dd{{margin:0}}
blockquote{{border-left:3px solid #c6c6c6;margin:12px 0;padding:8px 16px;white-space:pre-wrap}}
article{{border-top:1px solid #e0e0e0;padding:12px 0}}pre{{white-space:pre-wrap;font-size:12px}}
@media(max-width:600px){{dl{{grid-template-columns:1fr}}dd{{margin-bottom:10px}}}}
</style></head><body><p class="notice">{NOTICE}</p>
<h1>{_safe(report["report_title"])}</h1><p>{ATTRIBUTION}</p>
<h2>人工决定</h2><p>决定：{DECISION_LABELS[report["decision"]]}<br>
风险分数：{report["risk_score"]} / 100；风险等级：{RISK_LABELS[report["risk_level"]]}<br>
审查员：{_safe(report["decided_by"])}<br>决定时间：{_safe(report["decided_at"])}</p>
<p>决定理由：{_safe(report["decision_reason"])}</p>
<h2>版本与来源</h2><dl>{metadata}</dl><h2>风险发现</h2>
{findings or "<p>未发现规则风险；已由人工独立作出决定。</p>"}
<h2>审计摘要</h2><p>截至点：{_safe(_audit_cutoff(report))}</p>
<ul>{audit or "<li>没有可用的历史审计事件；来源仍为虚构演示。</li>"}</ul>
<details><summary>完整报告数据</summary><pre>{full_snapshot}</pre></details>
<p>本报告仅用于虚构数据演示和辅助决策，不构成法律意见。</p></body></html>"""


@lru_cache(maxsize=4)
def _register_font(path: str) -> str:
    resource = _font_resource(path)
    name = f"ReviewCJK-{resource['sha256'][:12]}"
    pdfmetrics.registerFont(TTFont(name, path))
    return name


def build_pdf_report(payload: dict[str, Any]) -> bytes:
    report = report_payload(payload)
    font = _register_font(_font_path())
    body = ParagraphStyle(
        "ReviewBody",
        fontName=font,
        fontSize=9.5,
        leading=15,
        textColor=HexColor("#161616"),
        wordWrap="CJK",
        splitLongWords=True,
        spaceAfter=7,
    )
    title = ParagraphStyle(
        "ReviewTitle",
        parent=body,
        fontSize=21,
        leading=29,
        spaceAfter=15,
    )
    section_heading = ParagraphStyle(
        "ReviewHeading",
        parent=body,
        fontSize=13,
        leading=20,
        spaceBefore=13,
        spaceAfter=9,
        keepWithNext=True,
    )
    metadata_style = ParagraphStyle(
        "ReviewMetadata",
        parent=body,
        fontSize=8.5,
        leading=13,
        textColor=HexColor("#525252"),
    )
    story: list[Any] = []

    def paragraph(value: object, style: ParagraphStyle = body) -> None:
        story.append(Paragraph(_safe(value).replace("\n", "<br/>"), style))

    paragraph(NOTICE, metadata_style)
    paragraph(report["report_title"], title)
    paragraph(ATTRIBUTION, metadata_style)
    paragraph("人工决定", section_heading)
    paragraph(
        f"决定：{DECISION_LABELS[report['decision']]}；风险分数：{report['risk_score']} / 100；"
        f"风险等级：{RISK_LABELS[report['risk_level']]}"
    )
    paragraph(
        f"审查员：{report['decided_by'] or 'unknown'}；"
        f"决定时间：{report['decided_at'] or 'unknown'}"
    )
    paragraph(f"决定理由：{report['decision_reason']}")
    paragraph("版本与来源", section_heading)
    for label, value in _meta_rows(report):
        paragraph(f"{label}：{value if value is not None else 'unknown'}", metadata_style)
    paragraph("风险发现", section_heading)
    if not report["findings"]:
        paragraph("未发现规则风险；已由人工独立作出决定。")
    for finding in report["findings"]:
        paragraph(f"{finding.get('rule_id')} · {finding.get('title')}", section_heading)
        paragraph(
            f"等级：{finding.get('severity')}；定位：{finding.get('locator', 'legacy')} "
            f"[{finding.get('start', 'unknown')}:{finding.get('end', 'unknown')}]；"
            f"偏移：{finding.get('offset_basis', 'unknown')}",
            metadata_style,
        )
        paragraph(f"证据：{finding.get('evidence', '')}")
        paragraph(f"建议：{finding.get('recommendation', '')}")
    paragraph("审计摘要", section_heading)
    paragraph(f"截至点：{_audit_cutoff(report)}")
    events = _audit_rows(report)
    if not events:
        paragraph("没有可用的历史审计事件；来源仍为虚构演示。")
    for event in events:
        paragraph(
            f"{event.get('occurred_at', event.get('timestamp', 'unknown'))} · "
            f"{event.get('event_type')} · {event.get('actor')} · {event.get('detail', '')}"
        )
    story.append(Spacer(1, 12))
    paragraph("本报告仅用于虚构数据演示和辅助决策，不构成法律意见。", metadata_style)
    paragraph(
        f"字体：{report['font_resource']['name']}；许可：{report['font_resource']['license']}",
        metadata_style,
    )
    paragraph(f"字体 SHA-256：{report['font_resource']['sha256']}", metadata_style)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=48,
        title=report["report_title"],
        author="AI Review Console - Built on Langflow",
        pageCompression=1,
        invariant=1,
    )

    def page_footer(pdf: Any, _: Any) -> None:
        pdf.saveState()
        pdf.setFont(font, 7)
        pdf.setFillColor(HexColor("#525252"))
        pdf.drawString(42, 25, "AI Review Console | Built on Langflow | SYNTHETIC DEMO ONLY")
        pdf.drawRightString(A4[0] - 42, 25, f"第 {pdf.getPageNumber()} 页")
        pdf.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()


def artifact_metadata(content: bytes) -> dict[str, object]:
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "bytes": len(content),
    }


def build_json_report(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        report_payload(payload), ensure_ascii=False, indent=2, allow_nan=False
    ).encode("utf-8")


def export_report_artifacts(
    snapshot: Mapping[str, Any],
    output_directory: str | Path,
    formats: Iterable[str] = REPORT_FORMATS,
    *,
    existing_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Publish requested formats atomically; never replace an existing registered artifact."""
    validate_decision_snapshot(snapshot)
    requested = list(dict.fromkeys(formats))
    if not requested or any(report_format not in REPORT_FORMATS for report_format in requested):
        raise ReportValidationError(
            "unsupported_report_format", "Requested report formats are unsupported"
        )
    root = Path(output_directory).resolve()
    decision_id = str(snapshot["decision_id"])
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", decision_id):
        raise ReportValidationError(
            "invalid_artifact_path", "Decision identifier is not a storage key"
        )
    directory = root / decision_id / str(snapshot["snapshot_hash"])
    if root not in directory.resolve().parents:
        raise ReportValidationError(
            "invalid_artifact_path", "Report storage path escapes the configured root"
        )
    directory.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any]] = {}
    errors: dict[str, dict[str, str]] = {}
    existing = existing_artifacts or {}
    for report_format, metadata in existing.items():
        if report_format not in REPORT_FORMATS or metadata.get("state", "ready") != "ready":
            continue
        path = Path(str(metadata.get("path", ""))).resolve()
        expected = directory / f"report.{report_format}"
        if expected.is_symlink() or path != expected.resolve() or not path.is_file():
            raise ReportValidationError(
                "artifact_mismatch", "Registered report storage path does not match"
            )
        content = path.read_bytes()
        if metadata.get("sha256") != hashlib.sha256(content).hexdigest():
            raise ReportValidationError("artifact_mismatch", "Registered report bytes do not match")
        recorded_size = metadata.get("bytes", metadata.get("size"))
        if recorded_size is not None and recorded_size != len(content):
            raise ReportValidationError(
                "artifact_mismatch", "Registered report size does not match"
            )
        artifacts[report_format] = dict(metadata)
    builders = {
        "json": build_json_report,
        "html": lambda value: build_html_report(value).encode("utf-8"),
        "pdf": build_pdf_report,
    }
    for report_format in requested:
        if report_format in artifacts:
            continue
        destination = directory / f"report.{report_format}"
        temporary: str | None = None
        try:
            if destination.is_symlink():
                raise ReportValidationError(
                    "artifact_conflict", "Report destination is a symbolic link"
                )
            content = builders[report_format](dict(snapshot))
            if destination.exists():
                with destination.open("rb") as existing_file:
                    if existing_file.read() != content:
                        raise ReportValidationError(
                            "artifact_conflict",
                            "An immutable report already exists with different bytes",
                        )
                    # Recover only unregistered, byte-identical publications from an
                    # older helper. Registered ready artifacts above remain untouched.
                    os.fchmod(existing_file.fileno(), 0o644)
            else:
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix=".report-", delete=False
                ) as handle:
                    temporary = handle.name
                    handle.write(content)
                    handle.flush()
                    # Synthetic-only reports cross UID 1000 -> 10001 through a
                    # read-only Compose mount. Publish completed, readable bytes.
                    os.fchmod(handle.fileno(), 0o644)
                    os.fsync(handle.fileno())
                try:
                    # A hard link publishes a completed file without overwriting a competing writer.
                    os.link(temporary, destination)
                except FileExistsError as exc:
                    if destination.read_bytes() != content:
                        raise ReportValidationError(
                            "artifact_conflict", "A concurrent report differs from this snapshot"
                        ) from exc
                os.unlink(temporary)
                temporary = None
            artifacts[report_format] = {
                "format": report_format,
                "state": "ready",
                "path": str(destination),
                "storage_key": str(destination.relative_to(root)),
                "snapshot_hash": snapshot["snapshot_hash"],
                "decision_id": decision_id,
                "template_version": REPORT_TEMPLATE_VERSION,
                **artifact_metadata(content),
            }
        except Exception as exc:
            # Failed temporary publications are quarantined for explicit later inventory.
            errors[report_format] = {
                "code": getattr(exc, "code", "report_generation_failed"),
                "detail": getattr(exc, "detail", "Report format could not be generated"),
            }
    state = (
        "ready"
        if all(item in artifacts for item in REPORT_FORMATS)
        else "partial"
        if artifacts
        else "failed"
    )
    return {
        "state": state,
        "artifacts": list(artifacts.values()),
        "errors": errors,
        "snapshot_hash": snapshot["snapshot_hash"],
    }
