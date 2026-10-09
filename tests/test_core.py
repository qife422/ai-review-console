import re
from pathlib import Path

from review_core.parsing import parse_document
from review_core.redaction import redact_text
from review_core.reporting import build_html_report, build_pdf_report
from review_core.risk import score_document


def test_parse_text_document(tmp_path: Path) -> None:
    document = tmp_path / "synthetic.md"
    document.write_text("SYNTHETIC DEMO DOCUMENT\n\n第一段。\n\n第二段。", encoding="utf-8")
    parsed = parse_document(document)
    assert parsed.filename == "synthetic.md"
    assert len(parsed.sections) == 3
    assert len(parsed.sha256) == 64


def test_redaction_is_deterministic_and_does_not_return_source_values() -> None:
    source = "联系人：林晞，电话 13800138001，邮箱 lin.xi@example.com。"
    first = redact_text(source)
    second = redact_text(source)
    assert first == second
    assert "13800138001" not in first.text
    assert "lin.xi@example.com" not in first.text
    assert first.to_dict()["count"] == 3


def test_risk_score_is_explainable() -> None:
    result = score_document("预付款90%，供应商承担全部损失，允许共享账号。")
    assert result.score == 74
    assert result.level == "high"
    assert {finding.rule_id for finding in result.findings} == {"FIN-003", "LEGAL-002", "SEC-004"}


def test_risk_evidence_does_not_cut_redaction_placeholders() -> None:
    result = score_document("[PERSON_01]，个人手机号 [PHONE_01]。供应方承担全部损失。")
    legal = next(finding for finding in result.findings if finding.rule_id == "LEGAL-002")
    assert "PERSON_01]" not in legal.evidence or "[PERSON_01]" in legal.evidence
    assert "PHONE_01]" not in legal.evidence or "[PHONE_01]" in legal.evidence


def test_reports_include_synthetic_and_langflow_notice() -> None:
    payload = {
        "title": "虚构审查",
        "document_hash": "a" * 64,
        "risk_score": 20,
        "risk_level": "low",
        "decision": "approved",
        "decision_reason": "虚构演示批准决定。",
        "findings": [],
    }
    html = build_html_report(payload)
    pdf = build_pdf_report(payload)
    assert "SYNTHETIC DEMO DATA ONLY" in html
    assert "Built on Langflow" in html
    assert pdf.startswith(b"%PDF")


def test_all_fixture_documents_are_synthetic_and_use_reserved_domains() -> None:
    fixture_dir = Path(__file__).parents[1] / "fixtures" / "documents"
    fixture_paths = sorted(path for path in fixture_dir.iterdir() if path.is_file())
    assert {path.suffix for path in fixture_paths} == {".docx", ".md", ".pdf", ".txt"}
    for path in fixture_paths:
        text = parse_document(path).text
        assert "SYNTHETIC DEMO DOCUMENT" in text
        domains = re.findall(r"@[A-Za-z0-9.-]+", text)
        reserved_domains = ("@example.com", "@example.org", "@example.net")
        assert all(domain.endswith(reserved_domains) for domain in domains)
