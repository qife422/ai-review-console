"""Bounded, real-container interruption and transport-failure acceptance.

Only the explicitly isolated upgrade project is allowed. Five new synthetic
cases and retained one-shot worker containers are the maximum write scope.
The normal worker is restarted in finally; no database/volume is deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "ai-review-console-upgrade"
COMPOSE = ["docker", "compose", "-p", PROJECT]
MODES = (
    "before_execution",
    "after_callback",
    "langflow_unavailable",
    "callback_unavailable",
    "langflow_401",
)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def command(args: list[str], timeout: int = 45) -> str:
    result = subprocess.run(args, cwd=ROOT, timeout=timeout, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{args[:3]} failed: {result.stderr[:1500]}")
    return result.stdout.strip()


def database() -> psycopg.Connection:
    return psycopg.connect(
        host="127.0.0.1",
        port=5433,
        user="review",
        password=os.getenv("POSTGRES_PASSWORD", "synthetic-demo-only"),
        dbname="review_console",
    )


def snapshot(case_id: str, job_id: str) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            "SELECT state, phase, attempt, retry_generation, execution_token, langflow_job_id, "
            "error_code, "
            "lease_until, result_hash FROM workflow_jobs WHERE id=%s AND case_id=%s",
            (job_id, case_id),
        ).fetchone()
        if row is None:
            raise AssertionError("Fault job is absent")
        result = dict(
            zip(
                (
                    "state",
                    "phase",
                    "attempt",
                    "retry_generation",
                    "token",
                    "langflow_job_id",
                    "error_code",
                    "lease_until",
                    "result_hash",
                ),
                row,
                strict=True,
            )
        )
        result["execution_token_sha256"] = digest((result.pop("token") or "").encode())
        result["lease_until"] = str(result["lease_until"]) if result["lease_until"] else None
        result["assessment_count"] = connection.execute(
            "SELECT count(*) FROM assessments a JOIN document_versions v "
            "ON a.document_version_id=v.id WHERE v.case_id=%s",
            (case_id,),
        ).fetchone()[0]
        result["scored_audit_count"] = connection.execute(
            "SELECT count(*) FROM audit_events WHERE case_id=%s AND event_type='case_scored'",
            (case_id,),
        ).fetchone()[0]
        result["job_count"] = connection.execute(
            "SELECT count(*) FROM workflow_jobs WHERE case_id=%s", (case_id,)
        ).fetchone()[0]
    return result


def wait_success(client: httpx.Client, case_id: str, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 155
    while time.monotonic() < deadline:
        current = snapshot(case_id, job_id)
        detail = client.get(f"/api/cases/{case_id}").raise_for_status().json()
        if current["state"] == "succeeded":
            assert detail["status"] == "pending_approval" and detail["decision"] is None
            assert current["assessment_count"] == current["scored_audit_count"] == 1
            assert current["langflow_job_id"] and not current["langflow_job_id"].startswith(
                "lf-demo"
            )
            return current
        if current["state"] == "failed":
            raise AssertionError(f"Recovery failed: {current}")
        time.sleep(1)
    raise TimeoutError("Real worker recovery did not finish in 155 seconds")


def one_shot(expected_id: str, mode: str, overrides: list[str]) -> dict[str, Any]:
    name = f"arc-fault-{mode.replace('_', '-')}-{uuid.uuid4().hex[:8]}"
    # This is process execution, not a production hook or an application edit.
    program = (
        "import time; from api.app.worker import Worker; "
        "from api.app.langflow_client import LangflowError; "
        f"w=Worker({name!r}); j=w.claim(); "
        f"assert j is not None and j.id=={expected_id!r}; "
    )
    if mode != "before_execution":
        program += "\ntry:\n w.run_job(j)\nexcept LangflowError as exc:\n w.record_failure(j,exc)\n"
    # PID 1 in a Linux namespace can ignore a self-generated fatal signal.
    # Kill it from the host only after the process confirms the precise stage.
    program += "\nprint('ARC_FAULT_READY',flush=True); time.sleep(45)\n"
    args = [*COMPOSE, "run", "--no-deps", "-d", "--name", name]
    for item in overrides:
        args.extend(["-e", item])
    container_id = command([*args, "worker", "python", "-c", program]).splitlines()[-1]
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        logs = command(["docker", "logs", container_id])
        if "ARC_FAULT_READY" in logs:
            break
        time.sleep(1)
    else:
        raise TimeoutError("Fault worker did not confirm the interruption stage")
    command(["docker", "kill", "--signal", "KILL", container_id])
    exit_code = command(["docker", "wait", container_id], timeout=15)
    assert exit_code == "137", "Fault container must end by actual SIGKILL"
    image = command(["docker", "inspect", "--format", "{{.Image}}", container_id])
    return {"container": name, "container_id": container_id, "image_id": image, "exit_code": 137}


def verify(client: httpx.Client, mode: str) -> dict[str, Any]:
    command([*COMPOSE, "stop", "-t", "10", "worker"])
    unique = uuid.uuid4().hex
    content = (
        f"SYNTHETIC DEMO DOCUMENT\nBuilt on Langflow\n容器故障验证 {mode} {unique}\n"
        "供应方承担全部损失，且不设责任上限。\n"
    ).encode()
    response = client.post(
        "/api/cases",
        headers={"Idempotency-Key": f"fault-upload-{unique}"},
        data={"title": f"虚构故障验证 {mode}", "synthetic_confirmed": "true"},
        files={"file": (f"fault-{unique}.txt", content, "text/plain")},
    )
    assert response.status_code == 202, response.text[:300]
    accepted = response.json()
    case_id, job_id = accepted["case_id"], accepted["job_id"]
    overrides = {
        "langflow_unavailable": ["LANGFLOW_URL=http://langflow:1"],
        "callback_unavailable": ["REVIEW_API_URL=http://api:1"],
        "langflow_401": ["LANGFLOW_SUPERUSER_PASSWORD=synthetic-deliberate-invalid-credential"],
    }.get(mode, [])
    started = time.monotonic()
    container = one_shot(job_id, mode, overrides)
    interrupted = snapshot(case_id, job_id)
    detail = client.get(f"/api/cases/{case_id}").raise_for_status().json()
    if mode == "before_execution":
        assert interrupted["state"] == "running" and interrupted["attempt"] == 1
        assert interrupted["langflow_job_id"] is None and interrupted["assessment_count"] == 0
        assert detail["risk_score"] is None
    elif mode == "after_callback":
        assert interrupted["state"] == "succeeded"
        assert interrupted["assessment_count"] == interrupted["scored_audit_count"] == 1
    else:
        expected_code = mode if mode != "langflow_401" else "langflow_auth_failed"
        assert interrupted["error_code"] == expected_code, interrupted
        assert interrupted["state"] == ("failed" if mode == "langflow_401" else "retry_wait")
        assert interrupted["assessment_count"] == 0 and detail["risk_score"] is None
    command([*COMPOSE, "start", "worker"])
    retry_job_id = None
    if mode == "langflow_401":
        assert detail["status"] == "failed"
        retry = client.post(
            f"/api/cases/{case_id}/retry",
            headers={"Idempotency-Key": f"fault-manual-retry-{unique}"},
            json={"job_id": job_id, "document_version_id": accepted["document_version_id"]},
        )
        assert retry.status_code == 202, retry.text[:300]
        retry_job_id = retry.json()["job_id"]
        assert retry_job_id != job_id
    recovered = wait_success(client, case_id, retry_job_id or job_id)
    # Give the restarted worker another claim cycle, not just the callback's response.
    time.sleep(3)
    repeated = snapshot(case_id, retry_job_id or job_id)
    assert repeated == recovered
    original_after_recovery = None
    if mode in {"before_execution", "after_callback"}:
        assert recovered["attempt"] == 1 and recovered["job_count"] == 1
        assert interrupted["execution_token_sha256"] == recovered["execution_token_sha256"]
    elif mode != "langflow_401":
        assert recovered["attempt"] == 2 and recovered["job_count"] == 1
        assert interrupted["execution_token_sha256"] != recovered["execution_token_sha256"]
    else:
        # A manual retry creates generation 1. Its own transient failures (for
        # example a real Langflow login 429) may retry within the Contract's
        # three-attempt limit; requiring exactly one attempt is not a guarantee.
        assert recovered["retry_generation"] == 1 and 1 <= recovered["attempt"] <= 3
        assert recovered["job_count"] == 2
        original_after_recovery = snapshot(case_id, job_id)
        assert original_after_recovery["state"] == "failed"
        assert original_after_recovery["error_code"] == "langflow_auth_failed"
        assert original_after_recovery["attempt"] == 1
        assert original_after_recovery["retry_generation"] == 0
        assert (
            original_after_recovery["execution_token_sha256"]
            == interrupted["execution_token_sha256"]
        )
        assert recovered["execution_token_sha256"] != interrupted["execution_token_sha256"]
    result = {
        "mode": mode,
        "case_id": case_id,
        "job_id": job_id,
        "retry_job_id": retry_job_id,
        "source_sha256": digest(content),
        "container": container,
        "interrupted_or_failed": interrupted,
        "recovered": recovered,
        "original_job_after_recovery": original_after_recovery,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "result": "passed",
    }
    print(
        json.dumps(
            {
                "mode": mode,
                "case_id": case_id,
                "result": "passed",
                "seconds": result["elapsed_seconds"],
            }
        ),
        flush=True,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, action="append")
    args = parser.parse_args()
    modes = tuple(args.mode) if args.mode else MODES
    if len(modes) > 5 or len(set(modes)) != len(modes):
        raise ValueError("Select at most five distinct fault modes")
    output = args.output.resolve()
    allowed = (Path(tempfile.gettempdir()).resolve(), Path("/private/tmp"))
    if not output.is_dir() or not any(output.is_relative_to(root) for root in allowed):
        raise ValueError("Use a fresh existing system temporary directory")
    destination = output / "faults.json"
    if destination.exists():
        raise FileExistsError("Never overwrite a fault manifest")
    with database() as connection:
        pending = connection.execute(
            "SELECT count(*) FROM workflow_jobs WHERE state IN ('queued','running','retry_wait')"
        ).fetchone()[0]
        assert pending == 0, "Wait for other validations to stop writing and finish their jobs"
    evidence: dict[str, Any] = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["AC-06", "AC-07"],
        "producer": "scripts/verify_faults.py",
        "producer_sha256": digest(Path(__file__).read_bytes()),
        "checked_at": datetime.now(UTC).isoformat(),
        "project": PROJECT,
        "selected_modes": list(modes),
        "cases": [],
        "limitations": (
            "Transport failures use real refused TCP connections in isolated one-shot workers; "
            "they do not stop the shared API/Langflow services. Timeout/429 mappings are separate "
            "contract tests. A recovered manual retry may encounter a real transient 429 "
            "and use up to three attempts in its new generation. Only selected modes are "
            "covered by this manifest. No existing case or business data is overwritten."
        ),
        "retention": "Fault containers and synthetic cases retained; no cleanup authorization",
    }
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15) as client:
            for mode in modes:
                evidence["cases"].append(verify(client, mode))
            health = client.get("/api/health").raise_for_status().json()
            evidence["final_health"] = health
        evidence["result"] = "passed"
    except Exception as exc:
        evidence["result"] = "failed"
        evidence["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        command([*COMPOSE, "start", "worker"])
        destination.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=2).encode())
        print(
            json.dumps({"manifest": str(destination), "sha256": digest(destination.read_bytes())}),
            flush=True,
        )


if __name__ == "__main__":
    main()
