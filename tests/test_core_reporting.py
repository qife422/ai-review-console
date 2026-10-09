import hashlib
import io
import json
import stat
from pathlib import Path

import pytest
from pypdf import PdfReader

from review_core import reporting
from review_core.redaction import REDACTION_POLICY_HASH, REDACTION_POLICY_VERSION
from review_core.reporting import (
    FONT_RESOURCE_SHA256,
    ReportValidationError,
    build_html_report,
    build_json_report,
    build_pdf_report,
    canonical_hash,
    export_report_artifacts,
    validate_decision_snapshot,
)
from review_core.risk import RULESET_HASH, RULESET_VERSION


def _snapshot(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "case_id": "case-synthetic",
        "document_version_id": "version-synthetic",
        "assessment_id": "assessment-synthetic",
        "decision_id": "decision-synthetic",
        "title": "星河虚构采购合同",
        "document_hash": "a" * 64,
        "hash_kind": "source_bytes_sha256",
        "source_kind": "uploaded_demo",
        "risk_score": 28,
        "risk_level": "medium",
        "ruleset_version": RULESET_VERSION,
        "ruleset_hash": RULESET_HASH,
        "redaction_policy_version": REDACTION_POLICY_VERSION,
        "redaction_policy_hash": REDACTION_POLICY_HASH,
        "decision": "changes_requested",
        "decision_reason": "请增加责任上限，移除共享账号条款后重新提交。",
        "decided_by": "虚构审查员林晞",
        "decided_at": "2026-10-08T16:00:00+00:00",
        "generated_at": "2026-10-08T17:00:00+00:00",
        "audit_cutoff": 12,
        "audit_events": [
            {
                "id": 12,
                "event_type": "decision_recorded",
                "actor": "虚构审查员林晞",
                "detail": "决定：要求修改，理由已保存。",
                "occurred_at": "2026-10-08T16:00:00+00:00",
            }
        ],
        "findings": [
            {
                "rule_id": "LEGAL-002",
                "title": "责任上限缺失或无限责任",
                "severity": "critical",
                "evidence": "供应商承担全部损失。",
                "recommendation": "增加明确、对等的责任上限。",
                "section_id": "section-0002",
                "locator": "table:1/row:1/cell:1",
                "start": 0,
                "end": 11,
                "offset_basis": "unicode_code_points",
            }
        ],
    }
    payload.update(changes)
    payload["snapshot_hash"] = canonical_hash(payload)
    return payload


@pytest.mark.parametrize(
    "decision", ["pending_approval", "ready", "failed", "processing", "unknown", None]
)
def test_reports_use_positive_decision_gate(decision: object) -> None:
    payload = _snapshot(decision=decision)
    for builder in (build_json_report, build_html_report, build_pdf_report):
        with pytest.raises(ReportValidationError) as exc:
            builder(payload)
        assert exc.value.code == "decision_required"


def test_bound_snapshot_rejects_mutation_missing_ids_and_score_level_mismatch() -> None:
    payload = _snapshot()
    payload["decision_reason"] = "迟到结果不得修改已记录的人工决定。"
    with pytest.raises(ReportValidationError) as exc:
        validate_decision_snapshot(payload)
    assert exc.value.code == "snapshot_hash_mismatch"
    with pytest.raises(ReportValidationError) as exc:
        validate_decision_snapshot(_snapshot(document_version_id=""))
    assert exc.value.code == "snapshot_incomplete"
    with pytest.raises(ReportValidationError) as exc:
        validate_decision_snapshot(_snapshot(risk_level="low"))
    assert exc.value.code == "assessment_required"


def test_formats_preserve_full_chinese_decision_snapshot_and_escape_html() -> None:
    payload = _snapshot(title="星河虚构合同<script>alert(1)</script>")
    json_report = json.loads(build_json_report(payload))
    html_report = build_html_report(payload)
    pdf_report = build_pdf_report(payload)
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf_report)).pages
    )
    assert json_report["snapshot_hash"] == payload["snapshot_hash"]
    assert json_report["report_title"] == "本次修订意见报告"
    for expected in (
        "本次修订意见报告",
        payload["decision_reason"],
        payload["decided_by"],
        "责任上限缺失或无限责任",
        payload["document_hash"],
        RULESET_VERSION,
        "Built on Langflow",
        "SYNTHETIC DEMO DATA ONLY",
        "decision-synthetic",
        "version-synthetic",
        "assessment-synthetic",
    ):
        assert expected in html_report
        assert expected in pdf_text.replace("\n", "")
    assert "<script>alert(1)</script>" not in html_report
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_report
    assert json_report["audit_events"] == payload["audit_events"]
    assert json_report["font_resource"]["sha256"] == FONT_RESOURCE_SHA256
    assert build_pdf_report(payload) == pdf_report
    assert "report_template_version" not in payload  # Reporting never mutates the saved snapshot.
    fonts = PdfReader(io.BytesIO(pdf_report)).pages[0]["/Resources"]["/Font"]
    assert any(
        font.get_object().get("/FontDescriptor", {}).get("/FontFile2")
        for font in fonts.values()
        if font.get_object().get("/FontDescriptor")
    )


def test_report_audit_cutoff_uses_the_api_snapshot_field() -> None:
    payload = _snapshot(audit_through_id=42)
    html_report = build_html_report(payload)
    pdf_text = "".join(
        (page.extract_text() or "").replace("\n", "")
        for page in PdfReader(io.BytesIO(build_pdf_report(payload))).pages
    )
    assert "截至点：42" in html_report
    assert "截至点：42" in pdf_text
    assert json.loads(build_json_report(payload))["audit_through_id"] == 42


def test_long_chinese_reason_and_findings_paginate_without_truncation() -> None:
    reason = "虚构理由：" + "应完善责任上限和验收条件。" * 60 + "结束标记。"
    findings = [
        {
            "rule_id": f"SYN-{index}",
            "title": f"虚构风险发现第{index}条",
            "severity": "high",
            "evidence": "虚构证据需要逐段核对。" * 60 + f"证据结束{index}。",
            "recommendation": "请修改后复核。",
            "locator": f"page:{index}",
            "section_id": f"section-{index:04d}",
            "start": 0,
            "end": 600,
            "offset_basis": "unicode_code_points",
        }
        for index in range(1, 8)
    ]
    payload = _snapshot(decision_reason=reason, findings=findings)
    reader = PdfReader(io.BytesIO(build_pdf_report(payload)))
    assert len(reader.pages) >= 3
    text = "".join((page.extract_text() or "").replace("\n", "") for page in reader.pages)
    assert reason in text
    assert all(f"证据结束{index}。" in text for index in range(1, 8))


def test_partial_report_retry_reuses_immutable_ready_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _snapshot()
    original_pdf_builder = reporting.build_pdf_report

    def failed_pdf(_: object) -> bytes:
        raise RuntimeError("synthetic format failure")

    monkeypatch.setattr(reporting, "build_pdf_report", failed_pdf)
    first = export_report_artifacts(snapshot, tmp_path)
    assert first["state"] == "partial"
    assert set(first["errors"]) == {"pdf"}
    existing = {item["format"]: item for item in first["artifacts"]}
    before = {item["format"]: Path(item["path"]).read_bytes() for item in first["artifacts"]}
    monkeypatch.setattr(reporting, "build_pdf_report", original_pdf_builder)
    second = export_report_artifacts(snapshot, tmp_path, ["pdf"], existing_artifacts=existing)
    assert second["state"] == "ready"
    assert not second["errors"]
    for item in second["artifacts"]:
        content = Path(item["path"]).read_bytes()
        assert item["sha256"] == hashlib.sha256(content).hexdigest()
        if item["format"] in before:
            assert content == before[item["format"]]


def test_atomic_reports_are_readable_across_container_uids_and_repair_only_unregistered_modes(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    generated = export_report_artifacts(snapshot, tmp_path)
    assert generated["state"] == "ready"
    before = {}
    for artifact in generated["artifacts"]:
        path = Path(artifact["path"])
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
        before[artifact["format"]] = (path.read_bytes(), path.stat().st_mtime_ns)
        # Simulate older Langflow output before API registration, not a formal artifact.
        path.chmod(0o600)
    repaired = export_report_artifacts(snapshot, tmp_path)
    assert repaired["state"] == "ready"
    for artifact in repaired["artifacts"]:
        path = Path(artifact["path"])
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before[artifact["format"]]
    ready = {item["format"]: item for item in repaired["artifacts"]}
    json_path = Path(ready["json"]["path"])
    json_path.chmod(0o600)
    reused = export_report_artifacts(snapshot, tmp_path, existing_artifacts=ready)
    assert reused["state"] == "ready"
    assert stat.S_IMODE(json_path.stat().st_mode) == 0o600  # Registered files are not changed.


def test_immutable_file_conflict_does_not_overwrite_and_registered_hash_is_checked(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    first = export_report_artifacts(snapshot, tmp_path)
    pdf = next(item for item in first["artifacts"] if item["format"] == "pdf")
    path = Path(pdf["path"])
    path.write_bytes(b"synthetic-corrupt-artifact")
    second = export_report_artifacts(snapshot, tmp_path, ["pdf"])
    assert second["errors"]["pdf"]["code"] == "artifact_conflict"
    assert path.read_bytes() == b"synthetic-corrupt-artifact"
    with pytest.raises(ReportValidationError) as exc:
        export_report_artifacts(snapshot, tmp_path, ["pdf"], existing_artifacts={"pdf": pdf})
    assert exc.value.code == "artifact_mismatch"


def test_missing_font_fails_only_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEW_REPORT_FONT", str(tmp_path / "missing.ttf"))
    result = export_report_artifacts(_snapshot(), tmp_path / "reports")
    assert result["state"] == "partial"
    assert {item["format"] for item in result["artifacts"]} == {"json", "html"}
    assert result["errors"]["pdf"]["code"] == "font_unavailable"
