from __future__ import annotations

import json
from pathlib import Path

from review_core.reporting import build_html_report, build_json_report, build_pdf_report
from review_core.risk import score_document

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "examples" / "reports"


def main() -> None:
    text = "预付款90%，供应方承担全部损失，允许共享账号。"
    assessment = score_document(text)
    payload = {
        "case_id": "RC-EXAMPLE-001",
        "title": "虚构供应服务协议",
        "document_hash": "8c803cd4d4582f87dd2c615b9029a4a92141a4e018485d85d6b2cc424882956d",
        "risk_score": assessment.score,
        "risk_level": assessment.level,
        "findings": [finding.__dict__ for finding in assessment.findings],
        "decision": "changes_requested",
        "decision_reason": "请增加责任上限，并移除共享账号条款。",
        "decided_by": "demo-reviewer",
        "ruleset_version": assessment.ruleset_version,
        "generated_at": "2026-09-01T08:00:00+08:00",
        "data_classification": "SYNTHETIC_DEMO_ONLY",
        "workflow_engine": "Langflow",
    }
    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / "synthetic-decision-report.json").write_bytes(build_json_report(payload))
    (DESTINATION / "synthetic-decision-report.html").write_text(
        build_html_report(payload), encoding="utf-8"
    )
    (DESTINATION / "synthetic-decision-report.pdf").write_bytes(build_pdf_report(payload))
    manifest = {
        path.name: {"bytes": path.stat().st_size}
        for path in sorted(DESTINATION.glob("synthetic-decision-report.*"))
    }
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
