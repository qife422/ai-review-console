"""SQLite transaction tests; simulated callbacks are not real Langflow evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.app.database import SessionLocal
from api.app.main import app
from api.app.models import Assessment, Decision, ReviewCase, WorkflowJob
from api.app.schemas import IntakeResult
from api.app.storage import reports_root
from review_core.parsing import parse_document
from review_core.redaction import redact_sections
from review_core.reporting import export_report_artifacts
from review_core.risk import score_sections

SERVICE_HEADERS = {"X-Service-Token": "synthetic-demo-service-token"}
SYNTHETIC_TEXT = (
    "SYNTHETIC DEMO DOCUMENT\n\n"
    "星河虚构采购合同。联系人邮箱：fictional@example.com。\n\n"
    "供应商承担全部损失，并允许共享账号。"
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as connection:
        yield connection


def _upload(
    client: TestClient, *, text: str = SYNTHETIC_TEXT, key: str | None = None
) -> dict[str, Any]:
    response = client.post(
        "/api/cases",
        headers={"Idempotency-Key": key or f"unit-upload-{uuid.uuid4().hex}"},
        data={"title": "虚构单元测试合同", "synthetic_confirmed": "true"},
        files={"file": ("synthetic.md", text.encode(), "text/markdown")},
    )
    assert response.status_code == 202, response.text
    return response.json()


def _intake_payload(upload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as session:
        job = session.get(WorkflowJob, upload["job_id"])
        job.state, job.phase, job.attempt = "running", "unit-callback", 1
        job.langflow_job_id = f"unit-simulated-{uuid.uuid4().hex}"
        session.commit()
        fixed = json.loads(job.payload_json)
        parsed = parse_document(Path(fixed["source_path"])).to_dict()
        redacted = redact_sections(parsed["sections"]).to_dict()
        assessment = score_sections(redacted["sections"]).to_dict()
        payload = {
            **fixed,
            "schema_version": "1.0",
            "job_id": job.id,
            "execution_token": job.execution_token,
            "payload_hash": job.payload_hash,
            "parsed_document": parsed,
            "redacted_document": redacted,
            "assessment": assessment,
            "warnings": [],
        }
    # The schemas intentionally exclude parser compatibility and extra redaction metadata.
    return IntakeResult.model_validate(payload).model_dump(mode="json")


def _pending(client: TestClient, *, text: str = SYNTHETIC_TEXT) -> dict[str, Any]:
    upload = _upload(client, text=text)
    result = client.post(
        "/api/integrations/langflow/results",
        headers=SERVICE_HEADERS,
        json=_intake_payload(upload),
    )
    assert result.status_code == 200, result.text
    return client.get(f"/api/cases/{upload['case_id']}").json()


def _decide(
    client: TestClient, case: dict[str, Any], *, decision: str = "changes_requested"
) -> dict[str, Any]:
    response = client.post(
        f"/api/cases/{case['id']}/decision",
        headers={
            "X-Reviewer": "unit-synthetic-reviewer",
            "Idempotency-Key": f"unit-{uuid.uuid4().hex}",
        },
        json={
            "decision": decision,
            "reason": "请完善责任上限并移除共享账号条款。",
            "document_version_id": case["current_document_version_id"],
            "assessment_id": case["assessment_id"],
            "expected_row_version": case["row_version"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _report_job(case: dict[str, Any], *, attempt: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    identifier = next(job["job_id"] for job in case["jobs"] if job["kind"] == "report")
    with SessionLocal() as session:
        job = session.get(WorkflowJob, identifier)
        job.state, job.phase, job.attempt = "running", "unit-callback", attempt
        job.langflow_job_id = f"unit-simulated-{uuid.uuid4().hex}"
        session.commit()
        fixed = json.loads(job.payload_json)
        envelope = {
            "job_id": job.id,
            "execution_token": job.execution_token,
            "payload_hash": job.payload_hash,
            "case_id": job.case_id,
            "document_version_id": job.document_version_id,
            "decision_id": job.decision_id,
            "snapshot_hash": fixed["snapshot"]["snapshot_hash"],
            "flow_id": job.flow_id,
            "flow_hash": job.flow_hash,
        }
    return envelope, fixed["snapshot"]


def _artifact_payload(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            field: artifact[field]
            for field in ("format", "storage_key", "sha256", "size", "template_version")
        }
        for artifact in result["artifacts"]
    ]


def _count(model: Any, case_id: str) -> int:
    with SessionLocal() as session:
        return session.scalar(
            select(func.count()).select_from(model).where(model.case_id == case_id)
        )


def test_upload_idempotency_keeps_null_assessment_and_one_job(client: TestClient) -> None:
    key = f"unit-upload-{uuid.uuid4().hex}"
    uploaded = _upload(client, key=key)
    repeated = _upload(client, key=key)
    assert repeated["case_id"] == uploaded["case_id"]
    assert repeated["job_id"] == uploaded["job_id"]
    assert repeated["duplicate"] is True
    detail = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert detail["status"] == "received"
    assert detail["risk_score"] is detail["risk_level"] is detail["assessment_id"] is None
    assert detail["flow_run_id"] is None
    assert detail["hash_kind"] == "source_bytes_sha256"
    assert detail["document_hash"] == hashlib.sha256(SYNTHETIC_TEXT.encode()).hexdigest()
    assert _count(WorkflowJob, uploaded["case_id"]) == 1
    conflict = client.post(
        "/api/cases",
        headers={"Idempotency-Key": key},
        data={"title": "另一份虚构合同", "synthetic_confirmed": "true"},
        files={"file": ("synthetic.md", SYNTHETIC_TEXT.encode(), "text/markdown")},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_upload_requires_explicit_demo_confirmation_and_idempotency_key(client: TestClient) -> None:
    for data, headers, expected in (
        (
            {"title": "虚构合同", "synthetic_confirmed": "false"},
            {"Idempotency-Key": "unit-rejected"},
            422,
        ),
        ({"title": "虚构合同", "synthetic_confirmed": "true"}, {}, 422),
    ):
        response = client.post(
            "/api/cases",
            data=data,
            headers=headers,
            files={"file": ("synthetic.txt", b"SYNTHETIC DEMO DOCUMENT", "text/plain")},
        )
        assert response.status_code == expected


def test_intake_authentication_duplicate_and_result_conflict_are_atomic(client: TestClient) -> None:
    uploaded = _upload(client)
    payload = _intake_payload(uploaded)
    unauthorized = client.post("/api/integrations/langflow/results", json=payload)
    assert unauthorized.status_code == 401
    accepted = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["duplicate"] is False
    before = client.get(f"/api/cases/{uploaded['case_id']}").json()
    duplicated = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert duplicated.status_code == 200
    assert duplicated.json()["duplicate"] is True
    after = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert after["assessment_id"] == before["assessment_id"]
    assert after["row_version"] == before["row_version"]
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Assessment)
                .where(Assessment.document_version_id == uploaded["document_version_id"])
            )
            == 1
        )
    assert (
        len([event for event in after["audit_events"] if event["event_type"] == "case_scored"]) == 1
    )
    conflicting = copy.deepcopy(payload)
    conflicting["warnings"] = ["不同的回调内容"]
    conflict = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=conflicting
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "callback_result_conflict"


@pytest.mark.parametrize(
    "field",
    ["execution_token", "payload_hash", "flow_id", "flow_hash", "document_version_id", "case_id"],
)
def test_intake_rejects_binding_changes_without_side_effects(
    client: TestClient, field: str
) -> None:
    uploaded = _upload(client)
    payload = _intake_payload(uploaded)
    payload[field] = f"wrong-{field}"
    response = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert response.status_code == 409
    assert response.json()["code"] == "callback_binding_conflict"
    detail = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert detail["risk_score"] is None
    assert detail["assessment_id"] is None
    assert len(detail["audit_events"]) == 1


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("source", "callback_version_conflict"),
        ("config", "callback_config_conflict"),
        ("redaction", "redaction_result_invalid"),
        ("score", "assessment_result_invalid"),
        ("evidence", "assessment_result_invalid"),
        ("sections", "sections_invalid"),
        ("marker", "synthetic_marker_missing"),
        ("text_limit", "text_too_large"),
    ],
)
def test_intake_rejects_hash_policy_and_deterministic_result_forgery(
    client: TestClient, mutation: str, code: str
) -> None:
    uploaded = _upload(client)
    payload = _intake_payload(uploaded)
    if mutation == "source":
        payload["source_sha256"] = "0" * 64
    elif mutation == "config":
        payload["ruleset_hash"] = "0" * 64
    elif mutation == "redaction":
        payload["redacted_document"]["sections"] = payload["parsed_document"]["sections"]
    elif mutation == "score":
        payload["assessment"]["score"] = 0
        payload["assessment"]["level"] = "low"
    elif mutation == "evidence":
        payload["assessment"]["findings"][0]["evidence"] = "伪造而不可定位的证据。"
    elif mutation == "sections":
        payload["parsed_document"]["sections"].append(payload["parsed_document"]["sections"][0])
    elif mutation == "marker":
        for section in payload["parsed_document"]["sections"]:
            section["text"] = section["text"].replace("SYNTHETIC DEMO DOCUMENT", "marker removed")
    elif mutation == "text_limit":
        payload["parsed_document"]["sections"][0]["text"] += "虚构" * 180_000
    response = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert response.status_code in {409, 422}
    assert response.json()["code"] == code
    detail = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert detail["assessment_id"] is None
    assert detail["risk_score"] is None


def test_unknown_callback_job_has_correlated_error_body(client: TestClient) -> None:
    uploaded = _upload(client)
    payload = _intake_payload(uploaded)
    payload["job_id"] = "JB-unit-not-found"
    response = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
    assert response.json()["request_id"]
    assert response.json()["retryable"] is False


def test_low_risk_still_requires_a_human_decision_and_finding_offsets_are_reproducible(
    client: TestClient,
) -> None:
    low = _pending(client, text="SYNTHETIC DEMO DOCUMENT\n\n虚构合同采用合理验收与独立账号。")
    assert low["risk_score"] == 0
    assert low["risk_level"] == "low"
    assert low["status"] == "pending_approval"
    assert low["decision"] is None
    assert client.get(f"/api/cases/{low['id']}/report/json").status_code == 409
    high = _pending(client)
    sections = {section["section_id"]: section for section in high["redacted_sections"]}
    for finding in high["findings"]:
        section = sections[finding["section_id"]]
        assert section["text"][finding["start"] : finding["end"]] == finding["evidence"]
        assert finding["locator"] == section["locator"]
    assert "fictional@example.com" not in high["redacted_text"]


def test_decision_version_gate_cas_and_request_idempotency_freeze_one_snapshot(
    client: TestClient,
) -> None:
    case = _pending(client)
    endpoint = f"/api/cases/{case['id']}/decision"
    reason = "已检查虚构条款，要求补充责任限制。"
    payload = {
        "decision": "changes_requested",
        "reason": f"  {reason}  ",
        "document_version_id": case["current_document_version_id"],
        "assessment_id": case["assessment_id"],
        "expected_row_version": case["row_version"],
    }
    assert client.post(endpoint, headers={"X-Reviewer": " "}, json=payload).status_code == 400
    missing = client.post(
        endpoint,
        headers={"X-Reviewer": "reviewer"},
        json={"decision": "approved", "reason": reason},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "version_required"
    stale = client.post(
        endpoint,
        headers={"X-Reviewer": "reviewer"},
        json={**payload, "document_version_id": "stale-version"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_document_version"
    key = f"unit-decision-{uuid.uuid4().hex}"
    headers = {"X-Reviewer": "  synthetic-reviewer  ", "Idempotency-Key": key}
    approved = client.post(endpoint, headers=headers, json=payload)
    assert approved.status_code == 200, approved.text
    saved = approved.json()
    assert saved["decision_reason"] == reason
    assert saved["decided_by"] == "synthetic-reviewer"
    assert saved["row_version"] == case["row_version"] + 1
    duplicate = client.post(endpoint, headers=headers, json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["decision_id"] == saved["decision_id"]
    assert duplicate.json()["row_version"] == saved["row_version"]
    conflict = client.post(endpoint, headers=headers, json={**payload, "decision": "rejected"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    loser = client.post(endpoint, headers={"X-Reviewer": "second-synthetic-reviewer"}, json=payload)
    assert loser.status_code == 409
    assert loser.json()["code"] == "decision_conflict"
    assert _count(Decision, case["id"]) == 1
    assert (
        len(
            [event for event in saved["audit_events"] if event["event_type"] == "decision_recorded"]
        )
        == 1
    )
    assert len([job for job in saved["jobs"] if job["kind"] == "report"]) == 1
    with SessionLocal() as session:
        decision = session.get(Decision, saved["decision_id"])
        snapshot = json.loads(decision.snapshot_json)
        assert snapshot["decision_reason"] == reason
        assert snapshot["audit_through_id"] == max(
            event["id"] for event in snapshot["audit_events"]
        )
        assert snapshot["snapshot_hash"] == decision.snapshot_hash
    assert {report["state"] for report in saved["reports"]} == {"queued"}


@pytest.mark.parametrize(
    "status", ["received", "processing", "pending_approval", "failed", "ready"]
)
def test_report_download_uses_positive_human_decision_gate(client: TestClient, status: str) -> None:
    uploaded = _upload(client)
    with SessionLocal() as session:
        case = session.get(ReviewCase, uploaded["case_id"])
        case.status = status
        session.commit()
    response = client.get(f"/api/cases/{uploaded['case_id']}/report/json")
    assert response.status_code == 409
    assert response.json()["code"] == "human_decision_required"


def test_report_callback_registers_verified_bytes_and_download_preserves_snapshot(
    client: TestClient,
) -> None:
    decided = _decide(client, _pending(client))
    envelope, snapshot = _report_job(decided)
    generated = export_report_artifacts(snapshot, reports_root())
    assert generated["state"] == "ready"
    callback = {**envelope, "artifacts": _artifact_payload(generated), "errors": []}
    accepted = client.post(
        "/api/integrations/langflow/reports", headers=SERVICE_HEADERS, json=callback
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["state"] == "ready"
    assert (
        client.post(
            "/api/integrations/langflow/reports", headers=SERVICE_HEADERS, json=callback
        ).status_code
        == 200
    )
    detail = client.get(f"/api/cases/{decided['id']}").json()
    assert detail["decision"] == "changes_requested"
    assert detail["decision_id"] == decided["decision_id"]
    assert (
        len([event for event in detail["audit_events"] if event["event_type"] == "report_ready"])
        == 3
    )
    assert {report["state"] for report in detail["reports"]} == {"ready"}
    for artifact in generated["artifacts"]:
        downloaded = client.get(f"/api/cases/{decided['id']}/report/{artifact['format']}")
        assert downloaded.status_code == 200
        assert hashlib.sha256(downloaded.content).hexdigest() == artifact["sha256"]
        assert downloaded.headers["X-Content-SHA256"] == artifact["sha256"]
    report = client.get(f"/api/cases/{decided['id']}/report/json").json()
    assert report["snapshot_hash"] == snapshot["snapshot_hash"]
    assert report["decision_reason"] == snapshot["decision_reason"]
    assert report["audit_through_id"] == snapshot["audit_through_id"]


def test_identical_late_intake_callback_cannot_change_a_decision_snapshot(
    client: TestClient,
) -> None:
    uploaded = _upload(client)
    payload = _intake_payload(uploaded)
    accepted = client.post(
        "/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload
    )
    assert accepted.status_code == 200
    pending = client.get(f"/api/cases/{uploaded['case_id']}").json()
    decided = _decide(client, pending)
    with SessionLocal() as session:
        before = session.get(Decision, decided["decision_id"]).snapshot_json
    late = client.post("/api/integrations/langflow/results", headers=SERVICE_HEADERS, json=payload)
    assert late.status_code == 200
    assert late.json()["duplicate"] is True
    after = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert after["decision_id"] == decided["decision_id"]
    assert after["row_version"] == decided["row_version"]
    with SessionLocal() as session:
        assert session.get(Decision, decided["decision_id"]).snapshot_json == before


def test_registered_report_download_rejects_missing_or_modified_bytes(client: TestClient) -> None:
    decided = _decide(client, _pending(client))
    envelope, snapshot = _report_job(decided)
    generated = export_report_artifacts(snapshot, reports_root())
    callback = {**envelope, "artifacts": _artifact_payload(generated), "errors": []}
    assert (
        client.post(
            "/api/integrations/langflow/reports", headers=SERVICE_HEADERS, json=callback
        ).status_code
        == 200
    )
    artifact = next(item for item in generated["artifacts"] if item["format"] == "json")
    path = Path(artifact["path"])
    original = path.read_bytes()
    # This is a unit-test runtime directory, not an evidence file or project source.
    path.write_bytes(b"synthetic-corrupted-test-content")
    rejected = client.get(f"/api/cases/{decided['id']}/report/json")
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "report_integrity_invalid"
    path.write_bytes(original)
    assert client.get(f"/api/cases/{decided['id']}/report/json").status_code == 200


def test_partial_report_manual_retry_preserves_ready_files_and_human_decision(
    client: TestClient,
) -> None:
    decided = _decide(client, _pending(client), decision="approved")
    envelope, snapshot = _report_job(decided, attempt=3)
    first = export_report_artifacts(snapshot, reports_root(), ["json", "html"])
    ready_hashes = {artifact["format"]: artifact["sha256"] for artifact in first["artifacts"]}
    callback = {
        **envelope,
        "artifacts": _artifact_payload(first),
        "errors": [{"format": "pdf", "code": "font_unavailable"}],
    }
    accepted = client.post(
        "/api/integrations/langflow/reports", headers=SERVICE_HEADERS, json=callback
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["missing_formats"] == ["pdf"]
    detail = client.get(f"/api/cases/{decided['id']}").json()
    assert detail["decision"] == "approved"
    assert detail["decision_id"] == decided["decision_id"]
    assert {item["format"]: item["state"] for item in detail["reports"]} == {
        "json": "ready",
        "html": "ready",
        "pdf": "failed",
    }
    key = f"unit-report-retry-{uuid.uuid4().hex}"
    retry_payload = {"snapshot_hash": snapshot["snapshot_hash"], "formats": ["pdf"]}
    endpoint = f"/api/cases/{decided['id']}/reports/retry"
    retry = client.post(endpoint, headers={"Idempotency-Key": key}, json=retry_payload)
    assert retry.status_code == 202, retry.text
    again = client.post(endpoint, headers={"Idempotency-Key": key}, json=retry_payload)
    assert again.status_code == 202
    assert again.json()["job_id"] == retry.json()["job_id"]
    with SessionLocal() as session:
        job = session.get(WorkflowJob, retry.json()["job_id"])
        job.state, job.attempt = "running", 1
        fixed = json.loads(job.payload_json)
        assert fixed["formats"] == ["pdf"]
        assert fixed["snapshot"] == snapshot
        new_envelope = {
            **envelope,
            "job_id": job.id,
            "execution_token": job.execution_token,
            "payload_hash": job.payload_hash,
        }
        session.commit()
    second = export_report_artifacts(snapshot, reports_root(), ["pdf"])
    finished = client.post(
        "/api/integrations/langflow/reports",
        headers=SERVICE_HEADERS,
        json={**new_envelope, "artifacts": _artifact_payload(second), "errors": []},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["state"] == "ready"
    for format_name, expected_hash in ready_hashes.items():
        downloaded = client.get(f"/api/cases/{decided['id']}/report/{format_name}")
        assert hashlib.sha256(downloaded.content).hexdigest() == expected_hash
    assert _count(Decision, decided["id"]) == 1
    assert _count(WorkflowJob, decided["id"]) == 3
    assert (
        client.post(
            endpoint, headers={"Idempotency-Key": f"unit-{uuid.uuid4().hex}"}, json=retry_payload
        ).status_code
        == 409
    )


def test_report_callback_checks_snapshot_path_and_content_integrity(client: TestClient) -> None:
    decided = _decide(client, _pending(client))
    envelope, snapshot = _report_job(decided)
    generated = export_report_artifacts(snapshot, reports_root(), ["json"])
    artifact = _artifact_payload(generated)[0]
    for altered, expected in (
        ({**envelope, "snapshot_hash": "0" * 64}, "report_snapshot_conflict"),
        (
            {**envelope, "artifacts": [{**artifact, "storage_key": "../outside.json"}]},
            "report_path_invalid",
        ),
        ({**envelope, "artifacts": [{**artifact, "sha256": "0" * 64}]}, "report_integrity_invalid"),
    ):
        body = {**envelope, "artifacts": [artifact], "errors": [], **altered}
        rejected = client.post(
            "/api/integrations/langflow/reports", headers=SERVICE_HEADERS, json=body
        )
        assert rejected.status_code in {409, 422}
        assert rejected.json()["code"] == expected
    detail = client.get(f"/api/cases/{decided['id']}").json()
    assert {item["state"] for item in detail["reports"]} == {"queued"}
    assert not [event for event in detail["audit_events"] if event["event_type"] == "report_ready"]


def test_failure_notification_is_idempotent_and_manual_intake_retry_preserves_history(
    client: TestClient,
) -> None:
    uploaded = _upload(client)
    with SessionLocal() as session:
        job = session.get(WorkflowJob, uploaded["job_id"])
        job.state, job.attempt, job.error_code = "failed", 3, "langflow_timeout"
        token = job.execution_token
        session.commit()
    endpoint = f"/api/integrations/langflow/jobs/{uploaded['job_id']}/failure"
    body = {"execution_token": token, "attempt": 3}
    first = client.post(endpoint, headers=SERVICE_HEADERS, json=body)
    assert first.status_code == 200, first.text
    before = client.get(f"/api/cases/{uploaded['case_id']}").json()
    repeated = client.post(endpoint, headers=SERVICE_HEADERS, json=body)
    assert repeated.status_code == 200, repeated.text
    after = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert after["row_version"] == before["row_version"]
    assert (
        len([event for event in after["audit_events"] if event["event_type"] == "intake_failed"])
        == 1
    )
    assert after["risk_score"] is after["assessment_id"] is None
    stale = client.post(
        endpoint, headers=SERVICE_HEADERS, json={**body, "execution_token": "stale"}
    )
    assert stale.status_code == 409
    key = f"unit-intake-retry-{uuid.uuid4().hex}"
    retry_body = {
        "document_version_id": uploaded["document_version_id"],
        "job_id": uploaded["job_id"],
    }
    retry_endpoint = f"/api/cases/{uploaded['case_id']}/retry"
    retry = client.post(retry_endpoint, headers={"Idempotency-Key": key}, json=retry_body)
    assert retry.status_code == 202, retry.text
    assert retry.json()["retry_generation"] == 1
    duplicated = client.post(retry_endpoint, headers={"Idempotency-Key": key}, json=retry_body)
    assert duplicated.status_code == 202
    assert duplicated.json()["job_id"] == retry.json()["job_id"]
    detail = client.get(f"/api/cases/{uploaded['case_id']}").json()
    assert detail["status"] == "received"
    assert len(detail["jobs"]) == 2
    assert any(
        job["job_id"] == uploaded["job_id"] and job["state"] == "failed" for job in detail["jobs"]
    )
