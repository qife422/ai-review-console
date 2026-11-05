"""Check strict benchmark gates against controlled timings and byte corruption."""

import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from scripts import validate_langflow as validation


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        self.value += 0.001
        return self.value


class Stack:
    def __init__(self, clock, upload_delay=0, corrupt=False):
        self.clock, self.upload_delay, self.corrupt = clock, upload_delay, corrupt
        self.cases = {}
        self.trace = []

    def response(self, path, data=None, status=200, content=None):
        return httpx.Response(
            status, json=data, content=content, request=httpx.Request("GET", "http://test" + path)
        )

    def post(self, path, **kwargs):
        self.trace.append(("POST", path))
        if path == "/api/cases":
            self.clock.value += self.upload_delay
            case_id = str(len(self.cases) + 1)
            filename, content, _ = kwargs["files"]["file"]
            unique = filename.removeprefix("benchmark-").removesuffix(".txt")
            self.cases[case_id] = {
                "status": "pending_approval",
                "document_hash": hashlib.sha256(content).hexdigest(),
                "original_text": unique,
                "current_document_version_id": "v1",
                "assessment_id": "a1",
                "row_version": 1,
                "jobs": [
                    {
                        "kind": "intake",
                        "job_id": "j" + case_id,
                        "state": "succeeded",
                        "langflow_job_id": "actual-intake",
                    }
                ],
                "reports": [],
            }
            assert len(content) == 1024 * 1024
            return self.response(path, {"case_id": case_id, "job_id": "j" + case_id}, 202)
        case_id = path.split("/")[3]
        detail = self.cases[case_id]
        snapshot = {
            "case_id": case_id,
            "decision": "approved",
            "decision_reason": kwargs["json"]["reason"],
        }
        bodies = {
            "json": json.dumps(snapshot).encode(),
            "html": b"<html>report</html>",
            "pdf": b"%PDF-test",
        }
        detail["bodies"] = bodies
        detail["reports"] = [
            {
                "format": fmt,
                "state": "ready",
                "id": fmt,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            for fmt, body in bodies.items()
        ]
        detail["jobs"].append(
            {
                "kind": "report",
                "state": "succeeded",
                "langflow_job_id": "actual-report",
                "created_at": "now",
            }
        )
        return self.response(path, {"decision": "approved"})

    def get(self, path, **kwargs):
        self.clock.value += getattr(self, "query_delay", 0)
        self.trace.append(("GET", path))
        if path in ("/api/cases", "/api/summary"):
            return self.response(path, [])
        case_id = path.split("/")[3]
        detail = self.cases[case_id]
        if "/report/" in path:
            body = detail["bodies"][path.rsplit("/", 1)[-1]]
            return self.response(path, content=body + (b"bad" if self.corrupt else b""))
        return self.response(path, {k: v for k, v in detail.items() if k != "bodies"})


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(validation.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(validation.time, "monotonic", clock.now)
    monkeypatch.setattr(
        validation.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            stdout=json.dumps({"ServerVersion": "test", "NCPU": 4, "MemTotal": 8 * 1024**3})
        ),
    )
    return clock


def benchmark(stack, **kwargs):
    return validation._benchmark(
        stack,
        20,
        reports=True,
        strict=True,
        ai_configuration={"rule_only_no_llm_nodes": True},
        **kwargs,
    )


def test_twenty_full_reports_mixed_queries_and_actual_hashes(clock):
    stack = Stack(clock)
    result = benchmark(stack)
    assert result["result"] == "passed" and all(result["targets_met"].values())
    assert len(result["samples"]) == 20
    assert all(len(s["reports"]) == 3 for s in result["samples"])
    assert all(r["count"] == 40 for r in result["query_routes"].values())
    assert {q["stage"] for q in result["query_samples"]} == {"intake_submitted", "report_submitted"}
    # Queries interleave each submitted intake/decision, before report download and next upload.
    assert stack.trace[:4] == [
        ("POST", "/api/cases"),
        ("GET", "/api/cases"),
        ("GET", "/api/summary"),
        ("GET", "/api/cases/1"),
    ]
    json.dumps(result, allow_nan=False)


def test_slow_upload_fails_targets_and_preserves_all_samples(clock):
    result = benchmark(Stack(clock, upload_delay=4))
    assert result["result"] == "failed"
    assert not result["targets_met"]["upload_p95_le_3_seconds"]
    assert len(result["samples"]) == 20
    assert all(s["success"] for s in result["samples"])


def test_corrupt_download_fails_without_losing_failure_evidence(clock):
    result = benchmark(Stack(clock, corrupt=True))
    assert result["result"] == "failed"
    assert not result["targets_met"]["sequential_tasks_not_lost"]
    assert len(result["samples"]) == 20
    assert all("Downloaded artifact" in s["error"] for s in result["samples"])
    assert not result["targets_met"]["each_complete_three_reports_le_120_seconds"]


def test_strict_requires_20_reports_and_verified_ai_configuration(clock):
    result = validation._benchmark(Stack(clock), 1, strict=True)
    assert result["result"] == "failed"
    assert not result["targets_met"]["exactly_20_samples"]
    assert not result["targets_met"]["reports_required"]
    assert not result["targets_met"]["ai_disabled_configuration_verified"]


def test_unknown_ai_node_is_not_disabled_proof():
    selected = {}
    for path in (validation.Path(__file__).parents[1] / "flows/generated").glob("*.json"):
        flow = json.loads(path.read_bytes())
        selected[flow["name"]] = flow
    assert validation._benchmark_ai_configuration(selected)["rule_only_no_llm_nodes"]
    selected["Document Review Intake"]["data"]["nodes"].append({"data": {"type": "LLM"}})
    assert not validation._benchmark_ai_configuration(selected)["rule_only_no_llm_nodes"]


def test_query_latency_gate_fails_without_lowering_threshold(clock):
    stack = Stack(clock)
    stack.query_delay = 0.6
    result = benchmark(stack)
    assert result["result"] == "failed"
    assert result["query_p95_seconds"] > 0.5
    assert not result["targets_met"]["query_p95_le_500_ms"]
    assert len(result["samples"]) == 20


def test_strict_main_writes_failed_evidence_before_nonzero(tmp_path, monkeypatch):
    import sys
    from unittest.mock import MagicMock

    selected = [
        {"id": name, "name": name, "data": {"nodes": []}}
        for name in ("Document Review Intake", "Document Review Decision")
    ]
    openapi = {
        "paths": {
            "/api/v1/build/{flow_id}/flow": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/schemas/Build"}}}
                    }
                }
            }
        },
        "components": {"schemas": {"Build": {"properties": {"data": {}}}}},
    }
    langflow = MagicMock()

    def request(method, path):
        payload = (
            openapi
            if path == "/openapi.json"
            else selected
            if path == "/api/v1/flows/"
            else {"data": {"nodes": []}}
        )
        return SimpleNamespace(json=lambda: payload)

    langflow.request.side_effect = request
    monkeypatch.setattr(validation, "LangflowClient", lambda: langflow)
    monkeypatch.setattr(validation, "require_langflow_version", lambda *args: "1.13.1")
    monkeypatch.setattr(validation, "find_template", lambda *args: True)
    monkeypatch.setattr(validation, "_validate_case", lambda *args: {})
    monkeypatch.setattr(validation, "_validate_markdown", lambda *args: {})
    monkeypatch.setattr(validation, "_validate_failure_retry", lambda *args: {})
    monkeypatch.setattr(
        validation,
        "_benchmark",
        lambda *args, **kwargs: {
            "result": "failed",
            "targets_met": {"upload_p95_le_3_seconds": False},
        },
    )
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate",
            "--benchmark-count",
            "20",
            "--benchmark-strict",
            "--benchmark-reports",
            "--evidence",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as exited:
        validation.main()
    assert exited.value.code == 1
    assert json.loads(output.read_text())["result"] == "failed"
    langflow.close.assert_called_once()
