"""Authenticated adapter for the pinned Langflow 1.11.6 Build API.

Each build receives a detached copy of a hash-checked trusted graph. Only the
runtime_json field is changed; no business execution PATCHes the stored Flow.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx

FLOW_NAMES = {"intake": "Document Review Intake", "report": "Document Review Decision"}
RUNTIME_NODES = {
    "intake": "SyntheticDocumentParser-review",
    "report": "DecisionReportExporter-review",
}


def canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def graph_hash(data: dict[str, Any]) -> str:
    return canonical_hash({"nodes": data.get("nodes", []), "edges": data.get("edges", [])})


def flow_configuration(kind: str) -> dict[str, Any]:
    manifest_path = os.getenv("LANGFLOW_FLOW_MANIFEST", "/app/config/langflow-flows.json")
    path = Path(manifest_path)
    if path.is_file():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        value = manifest.get("flows", {}).get(kind)
        if isinstance(value, dict) and value.get("id") and value.get("flow_hash"):
            return value
    prefix = "LANGFLOW_INTAKE" if kind == "intake" else "LANGFLOW_DECISION"
    flow_id, digest = os.getenv(f"{prefix}_FLOW_ID"), os.getenv(f"{prefix}_FLOW_HASH")
    if not flow_id or not digest:
        raise LangflowError("flow_not_configured", "Trusted Flow has not been published", False)
    return {
        "id": flow_id,
        "flow_hash": digest,
        "config_hash": os.getenv(f"{prefix}_CONFIG_HASH", ""),
        "runtime_node_id": RUNTIME_NODES[kind],
    }


class LangflowError(RuntimeError):
    def __init__(self, code: str, detail: str, retryable: bool = False):
        super().__init__(detail)
        self.code, self.detail, self.retryable = code, detail, retryable
        self.status_code: int | None = None


class LangflowClient:
    def __init__(self, base_url: str | None = None):
        self.client = httpx.Client(
            base_url=(base_url or os.getenv("LANGFLOW_URL", "http://localhost:7860")).rstrip("/"),
            timeout=httpx.Timeout(20, read=30),
        )
        self.headers: dict[str, str] = {}

    def close(self) -> None:
        self.client.close()

    def _authenticate(self) -> None:
        api_key = os.getenv("LANGFLOW_API_KEY", "")
        if api_key and not api_key.startswith("synthetic-demo"):
            self.headers = {"x-api-key": api_key}
            return
        username = os.getenv("LANGFLOW_SUPERUSER", "review-admin")
        password = os.getenv("LANGFLOW_SUPERUSER_PASSWORD", "")
        if not password:
            raise LangflowError("langflow_auth_unconfigured", "Langflow credentials are missing")
        response = self._send(
            "POST", "/api/v1/login", data={"username": username, "password": password}
        )
        token = response.json().get("access_token")
        if not token:
            raise LangflowError("langflow_auth_invalid", "Langflow did not return an access token")
        self.headers = {"Authorization": f"Bearer {token}"}

    def _send(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.client.request(method, endpoint, **kwargs)
        except httpx.TimeoutException as exc:
            raise LangflowError("langflow_timeout", "Langflow request timed out", True) from exc
        except httpx.HTTPError as exc:
            raise LangflowError("langflow_unavailable", "Langflow connection failed", True) from exc
        if response.is_error:
            code = "langflow_http_error"
            if response.status_code in {401, 403}:
                code = "langflow_auth_failed"
            elif response.status_code == 404:
                code = "langflow_not_found"
            elif response.status_code == 429:
                code = "langflow_rate_limited"
            failure = LangflowError(
                code,
                f"Langflow returned HTTP {response.status_code}",
                response.status_code == 429 or response.status_code >= 500,
            )
            failure.status_code = response.status_code
            raise failure
        return response

    def request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        if not self.headers:
            self._authenticate()
        try:
            return self._send(method, endpoint, headers=self.headers, **kwargs)
        except LangflowError as exc:
            if exc.status_code != 401:
                raise
            # Refresh an expired bearer token once; a rejected credential remains
            # an explicit, non-retryable job failure.
            self.headers = {}
            self._authenticate()
            return self._send(method, endpoint, headers=self.headers, **kwargs)

    def get_flow(self, flow_id: str, expected_hash: str) -> dict[str, Any]:
        flow = self.request("GET", f"/api/v1/flows/{flow_id}").json()
        data = flow.get("data")
        if not isinstance(data, dict) or graph_hash(data) != expected_hash:
            raise LangflowError("flow_hash_mismatch", "Published Flow differs from the job binding")
        return data

    def start(
        self,
        *,
        kind: str,
        flow_id: str,
        flow_hash: str,
        runtime: dict[str, Any],
        node_id: str | None = None,
    ) -> str:
        graph = copy.deepcopy(self.get_flow(flow_id, flow_hash))
        target_id = node_id or RUNTIME_NODES[kind]
        target = next((node for node in graph["nodes"] if node.get("id") == target_id), None)
        if target is None:
            raise LangflowError("flow_node_missing", "Trusted runtime input node is absent")
        template = target.get("data", {}).get("node", {}).get("template", {})
        field = template.get("runtime_json")
        if not isinstance(field, dict):
            raise LangflowError("flow_input_missing", "Trusted Flow has no runtime input")
        field["value"] = json.dumps(
            runtime, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        response = self.request(
            "POST",
            f"/api/v1/build/{flow_id}/flow",
            params={"event_delivery": "polling"},
            json={"data": graph},
        )
        job_id = response.json().get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise LangflowError("langflow_job_missing", "Build API did not return a job ID")
        return job_id

    def poll(self, upstream_job_id: str) -> list[dict[str, Any]]:
        response = self.request("GET", f"/api/v1/build/{upstream_job_id}/events")
        events: list[dict[str, Any]] = []
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LangflowError(
                    "langflow_events_invalid", "Build events were not valid JSON"
                ) from exc
            if isinstance(event, dict):
                events.append(event)
        return events

    def cancel(self, upstream_job_id: str) -> None:
        self.request("POST", f"/api/v1/build/{upstream_job_id}/cancel")


def output_objects(value: Any) -> list[dict[str, Any]]:
    """Locate Data output objects in nested Build vertex payloads."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if "job_id" in value and ("artifacts" in value or "gateway_result" in value):
            found.append(value)
        for item in value.values():
            found.extend(output_objects(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(output_objects(item))
    return found


def event_error(event: dict[str, Any]) -> LangflowError | None:
    data = event.get("data", {})
    if event.get("event") != "error":
        build_data = data.get("build_data", {}) if isinstance(data, dict) else {}
        if build_data.get("valid") is not False:
            return None
    text = json.dumps(data, ensure_ascii=False)
    # Preserve actionable classification without copying raw document text to logs.
    for code in (
        "requires_ocr",
        "unsupported_content",
        "synthetic_marker_missing",
        "empty_document",
        "invalid_utf8",
        "invalid_document",
        "encrypted_pdf",
        "invalid_pdf",
        "type_mismatch",
        "invalid_docx",
        "document_too_large",
        "text_too_large",
        "invalid_document_structure",
        "source_hash_mismatch",
        "policy_hash_mismatch",
        "ruleset_hash_mismatch",
    ):
        if code in text:
            return LangflowError(code, f"Document processing failed: {code}")
    if "401" in text or "403" in text:
        return LangflowError("callback_auth_failed", "Review result authentication failed")
    if "409" in text or "422" in text:
        return LangflowError("callback_validation_failed", "Review result was rejected")
    if "timeout" in text.lower() or "connection" in text.lower() or "503" in text:
        return LangflowError("callback_unavailable", "Review result could not be persisted", True)
    return LangflowError("langflow_component_failed", "A trusted Flow component failed")
