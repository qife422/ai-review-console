"""Unit-only transport/error contracts; MockTransport never contacts a service."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from api.app.langflow_client import (
    LangflowClient,
    LangflowError,
    encode_runtime,
    event_error,
    graph_hash,
)
from api.app.worker import Worker

runtime_spec = importlib.util.spec_from_file_location(
    "trusted_runtime_validator",
    Path(__file__).resolve().parents[1] / "custom_components/review_center/runtime.py",
)
runtime_module = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(runtime_module)
execution_context = runtime_module.execution_context


def bound_context() -> dict[str, Any]:
    return {
        "case_id": "RC-runtime-transport",
        "document_version_id": "DV-runtime-transport",
        "job_id": "JB-runtime-transport",
        "execution_token": "unit-execution-token",
        "payload_hash": "a" * 64,
        "flow_id": "unit-flow",
        "flow_hash": "b" * 64,
        "snapshot": {
            "evidence": '首行\n第二行："中文引号"；literal \\n；路径 C:\\notes\\new；\t尾行。',
        },
    }


def test_transport_survives_fixed_runtime_string_unescaping() -> None:
    context = bound_context()
    plain = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    # This is the actual lfx.utils.util.unescape_string implementation in 1.11.6.
    with pytest.raises(json.JSONDecodeError):
        json.loads(plain.replace("\\n", "\n"))
    encoded = encode_runtime(context)
    assert encoded.startswith("arc-runtime-v1:")
    assert "\\" not in encoded and "\n" not in encoded
    assert execution_context(encoded.replace("\\n", "\n")) == context
    assert context["payload_hash"] == "a" * 64


@pytest.mark.parametrize("value", ["arc-runtime-v1:not/base64%", "arc-runtime-v1:/w=="])
def test_invalid_transport_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="runtime_input_invalid"):
        execution_context(value)


def test_detached_build_encodes_only_runtime_input(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = {
        "nodes": [
            {
                "id": "DecisionReportExporter-review",
                "data": {"node": {"template": {"runtime_json": {"value": ""}}}},
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    original, requests = copy.deepcopy(graph), []
    client = LangflowClient()
    monkeypatch.setattr(client, "get_flow", lambda *_: graph)

    def request(method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        requests.append((method, endpoint, kwargs))
        return httpx.Response(200, json={"job_id": "unit-real-shaped-upstream"})

    monkeypatch.setattr(client, "request", request)
    try:
        context = bound_context()
        upstream = client.start(
            kind="report", flow_id="unit-flow", flow_hash=graph_hash(graph), runtime=context
        )
        assert upstream == "unit-real-shaped-upstream"
        assert graph == original
        assert len(requests) == 1 and requests[0][0] == "POST"
        detached = requests[0][2]["json"]["data"]
        encoded = detached["nodes"][0]["data"]["node"]["template"]["runtime_json"]["value"]
        assert execution_context(encoded.replace("\\n", "\n")) == context
        detached["nodes"][0]["data"]["node"]["template"]["runtime_json"]["value"] = ""
        assert detached == original
    finally:
        client.close()


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "langflow_auth_failed", False),
        (403, "langflow_auth_failed", False),
        (404, "langflow_not_found", False),
        (422, "langflow_http_error", False),
        (429, "langflow_rate_limited", True),
        (500, "langflow_http_error", True),
        (502, "langflow_http_error", True),
        (503, "langflow_http_error", True),
        (504, "langflow_http_error", True),
    ],
)
def test_unit_adapter_http_status_contract(status: int, code: str, retryable: bool) -> None:
    client = LangflowClient()
    client.client.close()
    client.client = httpx.Client(
        base_url="http://unit-langflow.invalid",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json={"unit": True})),
    )
    try:
        with pytest.raises(LangflowError) as raised:
            client._send("GET", "/unit-only")
        assert raised.value.code == code
        assert raised.value.status_code == status
        assert raised.value.retryable is retryable
    finally:
        client.close()


@pytest.mark.parametrize(
    ("failure_type", "code"),
    [(httpx.ReadTimeout, "langflow_timeout"), (httpx.ConnectError, "langflow_unavailable")],
)
def test_unit_adapter_network_error_contract(
    failure_type: type[httpx.HTTPError], code: str
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise failure_type("Unit-only network failure", request=request)

    client = LangflowClient()
    client.client.close()
    client.client = httpx.Client(
        base_url="http://unit-langflow.invalid", transport=httpx.MockTransport(fail)
    )
    try:
        with pytest.raises(LangflowError) as raised:
            client._send("GET", "/unit-only")
        assert raised.value.code == code and raised.value.retryable
    finally:
        client.close()


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "callback_auth_failed", False),
        (403, "callback_auth_failed", False),
        (409, "callback_validation_failed", False),
        (422, "callback_validation_failed", False),
        (429, "callback_unavailable", True),
        (500, "callback_unavailable", True),
        (502, "callback_unavailable", True),
        (503, "callback_unavailable", True),
        (504, "callback_unavailable", True),
    ],
)
def test_unit_gateway_build_event_status_contract(status: int, code: str, retryable: bool) -> None:
    failure = event_error(
        {
            "event": "error",
            "data": {
                "exception": f"HTTPStatusError: Client error '{status} unit failure' for url",
            },
        }
    )
    assert failure is not None
    assert failure.code == code and failure.retryable is retryable


@pytest.mark.parametrize(
    ("status", "body", "retryable"),
    [
        (401, {"code": "unit_auth", "retryable": True}, False),
        (403, {"code": "unit_auth", "retryable": True}, False),
        (422, {"code": "unit_validation", "retryable": True}, False),
        (409, {"code": "unit_conflict"}, False),
        (409, {"code": "report_file_missing", "retryable": True}, True),
        (429, {"code": "unit_throttle"}, True),
        (500, {"code": "unit_server_failure"}, True),
        (502, {"code": "unit_server_failure", "retryable": False}, True),
        (503, {"code": "unit_server_failure"}, True),
        (504, {"code": "unit_server_failure"}, True),
    ],
)
def test_unit_worker_callback_http_contract(
    status: int, body: dict[str, Any], retryable: bool
) -> None:
    worker = Worker("unit-error-contract")
    worker.api.close()
    worker.api = httpx.Client(
        base_url="http://unit-review-api.invalid",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body)),
    )
    try:
        with pytest.raises(LangflowError) as raised:
            worker._post("/unit-only", {"unit": True})
        assert raised.value.code == body["code"]
        assert raised.value.retryable is retryable
    finally:
        worker.api.close()
        worker.langflow.close()


@pytest.mark.parametrize("failure_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_unit_worker_callback_network_contract(failure_type: type[httpx.HTTPError]) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise failure_type("Unit-only callback failure", request=request)

    worker = Worker("unit-error-contract")
    worker.api.close()
    worker.api = httpx.Client(
        base_url="http://unit-review-api.invalid", transport=httpx.MockTransport(fail)
    )
    try:
        with pytest.raises(LangflowError) as raised:
            worker._post("/unit-only", {"unit": True})
        assert raised.value.code == "callback_unavailable" and raised.value.retryable
    finally:
        worker.api.close()
        worker.langflow.close()


@pytest.mark.parametrize("accepted", [True, False])
def test_unit_worker_requires_accepted_callback(accepted: bool) -> None:
    worker = Worker("unit-error-contract")
    worker.api.close()
    worker.api = httpx.Client(
        base_url="http://unit-review-api.invalid",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"accepted": accepted})),
    )
    try:
        if accepted:
            assert worker._post("/unit-only", {"unit": True}) == {"accepted": True}
        else:
            with pytest.raises(LangflowError) as raised:
                worker._post("/unit-only", {"unit": True})
            assert raised.value.code == "callback_not_persisted" and not raised.value.retryable
    finally:
        worker.api.close()
        worker.langflow.close()
