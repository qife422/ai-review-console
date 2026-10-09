from fastapi.testclient import TestClient

from api.app.main import app


def test_dashboard_and_case_detail() -> None:
    with TestClient(app) as client:
        summary = client.get("/api/summary")
        assert summary.status_code == 200
        assert summary.json()["total_cases"] == 12
        cases = client.get("/api/cases", params={"status": "pending_approval"})
        assert cases.status_code == 200
        assert len(cases.json()) >= 1
        case_id = cases.json()[0]["id"]
        detail = client.get(f"/api/cases/{case_id}")
        assert detail.status_code == 200
        assert detail.json()["flow_run_id"] is None
        assert detail.json()["source"]["legacy_flow_label"].startswith("lf-demo-")
        assert detail.json()["hash_kind"] == "synthetic_text"


def test_decision_requires_reviewer_and_reason() -> None:
    with TestClient(app) as client:
        pending = client.get("/api/cases", params={"status": "pending_approval"}).json()[0]
        missing_reviewer = client.post(
            f"/api/cases/{pending['id']}/decision",
            json={"decision": "approved", "reason": "已检查全部虚构条款。"},
        )
        assert missing_reviewer.status_code == 400
        decided = client.post(
            f"/api/cases/{pending['id']}/decision",
            headers={"X-Reviewer": "demo-reviewer"},
            json={"decision": "approved", "reason": "已检查全部虚构条款。"},
        )
        assert decided.status_code == 200
        assert decided.json()["decision"] == "approved"
        duplicate = client.post(
            f"/api/cases/{pending['id']}/decision",
            headers={"X-Reviewer": "demo-reviewer"},
            json={"decision": "rejected", "reason": "不应覆盖已经记录的最终决定。"},
        )
        assert duplicate.status_code == 409
        report = client.get(f"/api/cases/{pending['id']}/report/json")
        assert report.status_code == 409
        assert report.json()["code"] == "report_not_ready"
        assert all(item["state"] == "queued" for item in decided.json()["reports"])
        assert len([job for job in decided.json()["jobs"] if job["kind"] == "report"]) == 1


def test_langflow_task_gateway_requires_service_token() -> None:
    payload = {
        "case_id": "RC-260901-001",
        "status": "pending_approval",
        "risk_score": 52,
        "risk_level": "high",
        "idempotency_key": "RC-260901-001:2026.09-demo.1",
    }
    with TestClient(app) as client:
        unauthorized = client.post("/api/integrations/langflow/tasks", json=payload)
        assert unauthorized.status_code == 401
        accepted = client.post(
            "/api/integrations/langflow/tasks",
            headers={"X-Service-Token": "synthetic-demo-service-token"},
            json=payload,
        )
        assert accepted.status_code == 422
        assert accepted.json()["code"] == "legacy_callback_incomplete"
