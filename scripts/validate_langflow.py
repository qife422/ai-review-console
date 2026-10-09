"""Exercise dynamic input, persistence, decisions and reports on a real stack.

Creates three explicitly synthetic cases in the selected API database. No Flow
is PATCHed and no existing document, decision or report is overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap_langflow import COMPONENTS, find_template  # noqa: E402

from api.app.langflow_client import LangflowClient, graph_hash  # noqa: E402


def _items(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def _json(response: httpx.Response, expected: int = 200) -> Any:
    if response.status_code != expected:
        raise RuntimeError(
            f"Expected HTTP {expected}; got {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def _wait_case(client: httpx.Client, case_id: str, *, reports: bool = False) -> dict[str, Any]:
    deadline = time.monotonic() + 160
    while time.monotonic() < deadline:
        detail = _json(client.get(f"/api/cases/{case_id}"))
        if reports:
            artifacts = detail.get("reports", [])
            if len(artifacts) >= 3 and all(item["state"] == "ready" for item in artifacts):
                return detail
            report_jobs = [job for job in detail.get("jobs", []) if job.get("kind") == "report"]
            if report_jobs and report_jobs[-1]["state"] == "failed":
                raise RuntimeError(f"Report job failed: {report_jobs[-1]}")
        elif detail["status"] == "pending_approval":
            return detail
        elif detail["status"] == "failed":
            raise RuntimeError(f"Intake failed: {detail.get('jobs')}")
        time.sleep(1)
    raise TimeoutError(f"Case {case_id} did not reach the requested state")


def _validate_case(client: httpx.Client, decision: str, index: int) -> dict[str, Any]:
    unique = uuid.uuid4().hex
    clauses = (
        "供应方承担全部损失，且不设责任上限。",
        "客户预付款90%，服务方可单方变更结算规则。",
        "联系人：林澈，个人手机号13800138001。使用共享账号和明文密码。",
    )
    content = (
        f"SYNTHETIC DEMO DOCUMENT\nBuilt on Langflow\n执行验证 {unique}\n\n{clauses[index]}\n"
    ).encode()
    upload_key = f"flow-validation-upload-{unique}"
    upload_args = {
        "headers": {"Idempotency-Key": upload_key},
        "data": {"title": f"真实工作流虚构验证 {decision}", "synthetic_confirmed": "true"},
        "files": {"file": (f"flow-validation-{unique}.txt", content, "text/plain")},
    }
    accepted = _json(client.post("/api/cases", **upload_args), 202)
    case_id = accepted["case_id"]
    duplicate = _json(client.post("/api/cases", **upload_args), 202)
    if duplicate["case_id"] != case_id:
        raise AssertionError("Same-key upload created a duplicate case")
    detail = _wait_case(client, case_id)
    if (
        detail["source_kind"] != "uploaded_demo"
        or detail["document_hash"] != hashlib.sha256(content).hexdigest()
        or unique not in detail["original_text"]
        or not detail["findings"]
    ):
        raise AssertionError("Intake output was not bound to the newly uploaded bytes")
    intake_jobs = [item for item in detail["jobs"] if item["kind"] == "intake"]
    upstream_id = intake_jobs[-1].get("langflow_job_id") if intake_jobs else None
    if not upstream_id or str(upstream_id).startswith("lf-demo"):
        raise AssertionError("A real Langflow job ID is required")
    reason = f"虚构验证完成：审查员依据规则证据记录{decision}，并核对中文报告。"
    decided = _json(
        client.post(
            f"/api/cases/{case_id}/decision",
            headers={
                "X-Reviewer": "synthetic-flow-validator",
                "Idempotency-Key": f"flow-validation-decision-{unique}",
            },
            json={
                "decision": decision,
                "reason": reason,
                "document_version_id": detail["current_document_version_id"],
                "assessment_id": detail["assessment_id"],
                "expected_row_version": detail["row_version"],
            },
        )
    )
    if decided["decision"] != decision:
        raise AssertionError("The human decision was not recorded")
    detail = _wait_case(client, case_id, reports=True)
    registered = []
    for artifact in detail["reports"]:
        report_format = artifact["format"]
        response = client.get(
            f"/api/cases/{case_id}/report/{report_format}",
            params={"report_id": artifact.get("report_id", artifact.get("id"))},
        )
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        if digest != artifact["sha256"] or len(response.content) != artifact["bytes"]:
            raise AssertionError("Downloaded artifact does not match registered bytes")
        if report_format == "json":
            snapshot = response.json()
            if (
                snapshot["case_id"] != case_id
                or snapshot["decision"] != decision
                or snapshot["decision_reason"] != reason
            ):
                raise AssertionError("Report used a different decision snapshot")
        registered.append(
            {"format": report_format, "sha256": digest, "bytes": len(response.content)}
        )
    report_jobs = [item for item in detail["jobs"] if item["kind"] == "report"]
    if not report_jobs[-1].get("langflow_job_id"):
        raise AssertionError("Report did not execute a real Decision Flow")
    return {
        "case_id": case_id,
        "document_version_id": accepted["document_version_id"],
        "intake_job_id": accepted["job_id"],
        "intake_langflow_job_id": upstream_id,
        "decision": decision,
        "decision_id": detail["decision_id"],
        "report_langflow_job_id": report_jobs[-1]["langflow_job_id"],
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "reports": registered,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.getenv("REVIEW_API_URL", "http://localhost:8080"))
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    langflow = LangflowClient()
    try:
        component_index = langflow.request("GET", "/api/v1/all").json()
        missing = [name for name in COMPONENTS if not find_template(component_index, name)]
        if missing:
            raise RuntimeError(f"Missing trusted components: {', '.join(missing)}")
        flow_items = _items(langflow.request("GET", "/api/v1/flows/").json())
        selected = {
            name: next((item for item in flow_items if item.get("name") == name), None)
            for name in ("Document Review Intake", "Document Review Decision")
        }
        if not all(selected.values()):
            raise RuntimeError("Published review Flows are missing")
        before = {name: graph_hash(item["data"]) for name, item in selected.items() if item}
        openapi = langflow.request("GET", "/openapi.json").json()
        if openapi.get("info", {}).get("version") != "1.11.6":
            raise AssertionError("Runtime differs from the pinned Langflow 1.11.6 contract")
        build_operation = openapi["paths"]["/api/v1/build/{flow_id}/flow"]["post"]
        if not build_operation.get("requestBody"):
            raise AssertionError("Build API does not expose its per-execution input body")
        body_schema = build_operation["requestBody"]["content"]["application/json"]["schema"]
        schema_name = body_schema["$ref"].rsplit("/", 1)[-1]
        if "data" not in openapi["components"]["schemas"][schema_name]["properties"]:
            raise AssertionError("Build API does not expose a per-run data override")
        with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=30) as api:
            results = [
                _validate_case(api, decision, index)
                for index, decision in enumerate(("approved", "rejected", "changes_requested"))
            ]
        after = {
            name: graph_hash(langflow.request("GET", f"/api/v1/flows/{item['id']}").json()["data"])
            for name, item in selected.items()
            if item
        }
        if before != after:
            raise AssertionError("A per-case execution mutated a stored shared Flow")
        evidence = {
            "contract": "ARC-UPGRADE@0.1.0",
            "producer": "scripts/validate_langflow.py",
            "checked_at": datetime.now(UTC).isoformat(),
            "langflow_version": "1.11.6",
            "acceptance": ["AC-04", "AC-13", "AC-18"],
            "component_count": len(COMPONENTS),
            "build_input": "authenticated Build API data override; no per-case PATCH",
            "stored_flow_hashes_before": before,
            "stored_flow_hashes_after": after,
            "cases": results,
            "result": "passed",
        }
        if args.evidence:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        langflow.close()


if __name__ == "__main__":
    main()
