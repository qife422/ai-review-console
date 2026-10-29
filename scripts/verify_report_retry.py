"""Real partial-report/retry proof on the isolated upgrade project only.

Creates at most one synthetic case. A temporary Compose overlay changes only
Langflow's REVIEW_REPORT_FONT, then finally restores its original image/env,
mounts and published Flow hashes. No image build/pull, cleanup or volume change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "ai-review-console-upgrade"
BASE = ROOT / "docker-compose.yml"
COMPOSE = ["docker", "compose", "--project-directory", str(ROOT), "-p", PROJECT, "-f", str(BASE)]
API = "http://127.0.0.1:8000"
MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 32
ACTIVE = {"queued", "running", "retry_wait"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class Proof:
    def __init__(self, output: Path):
        self.output = output
        self.records: list[dict[str, Any]] = []
        self.result: dict[str, Any] = {
            "contract": "ARC-UPGRADE@0.1.0",
            "acceptance": ["AC-14"],
            "producer": "scripts/verify_report_retry.py",
            "producer_sha256": digest(Path(__file__).read_bytes()),
            "spec_sha256": digest((ROOT / "docs/UPGRADE_SPEC.md").read_bytes()),
            "started_at": now(),
            "project": PROJECT,
            "api": API,
            "case_limit": 1,
            "result": "failed",
            "restoration": {"required": False},
            "retention": "Synthetic case, reports and temporary proof retained; no cleanup.",
            "limitations": (
                "Only missing-font PDF failure and failed-format manual retry are covered."
            ),
        }

    def write(self, name: str, content: bytes) -> None:
        files = [item for item in self.output.rglob("*") if item.is_file()]
        if (
            len(files) + 1 > MAX_FILES
            or sum(p.stat().st_size for p in files) + len(content) > MAX_BYTES
        ):
            raise RuntimeError("Proof output capacity exceeded; no cleanup is performed")
        with (self.output / name).open("xb") as target:
            target.write(content)

    def save(self, name: str, value: object) -> None:
        self.write(name, json.dumps(value, ensure_ascii=False, indent=2).encode())

    def command(self, label: str, args: list[str], timeout: int = 60) -> str:
        started = now()
        completed = subprocess.run(args, cwd=ROOT, timeout=timeout, capture_output=True, text=True)
        self.records.append(
            {
                "label": label,
                "argv": args,
                "started_at": started,
                "ended_at": now(),
                "exit_code": completed.returncode,
                "stdout_sha256": digest(completed.stdout.encode()),
                "stderr_sha256": digest(completed.stderr.encode()),
                "raw_output_recorded": False,
            }
        )
        if completed.returncode:
            # Inspect/config output can contain secrets; keep only fingerprints.
            raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
        return completed.stdout.strip()

    def container(self, service: str) -> dict[str, Any]:
        identifier = self.command(f"{service}-id", [*COMPOSE, "ps", "-q", service])
        if not identifier or "\n" in identifier:
            raise RuntimeError(f"Exactly one running {service} container is required")
        value = json.loads(self.command(f"{service}-inspect", ["docker", "inspect", identifier]))[0]
        labels = value["Config"].get("Labels") or {}
        if (
            labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
        ):
            raise RuntimeError("Container is outside the fixed isolated project/service")
        if not value["State"].get("Running"):
            raise RuntimeError(f"{service} is not running")
        return value

    @staticmethod
    def environment(container: dict[str, Any]) -> dict[str, str]:
        return dict(
            item.split("=", 1) for item in container["Config"].get("Env", []) if "=" in item
        )

    @classmethod
    def identity(cls, container: dict[str, Any]) -> dict[str, Any]:
        environment = cls.environment(container)
        return {
            "image_id": container["Image"],
            "environment_sha256": digest(canonical(environment)),
            "mounts": sorted(
                [
                    {
                        "type": item["Type"],
                        "name": item.get("Name"),
                        "destination": item["Destination"],
                        "rw": item["RW"],
                    }
                    for item in container["Mounts"]
                ],
                key=lambda item: item["destination"],
            ),
            "networks": sorted(container["NetworkSettings"]["Networks"]),
            "health": container["State"].get("Health", {}).get("Status"),
            "font_override_present": "REVIEW_REPORT_FONT" in environment,
        }

    def ensure_tag(self, container: dict[str, Any]) -> None:
        actual = self.command(
            "local-image-id",
            ["docker", "image", "inspect", "--format", "{{.Id}}", container["Config"]["Image"]],
        )
        if actual != container["Image"]:
            raise RuntimeError("Compose image tag no longer points to the original running image")

    def health(self, timeout: int = 240) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self.container("langflow")
            if current["State"].get("Health", {}).get("Status") == "healthy":
                return current
            time.sleep(2)
        raise TimeoutError("Langflow did not regain its Compose health within 240 seconds")

    def counts(self, case_id: str | None = None) -> dict[str, Any]:
        program = (
            "import json; from sqlalchemy import text; from api.app.database import engine; "
            "c=engine.connect(); "
            "r={'active_jobs':c.execute(text(\"SELECT count(*) FROM workflow_jobs WHERE state IN "
            "('queued','running','retry_wait')\")).scalar_one(),"
            "'case_count':c.execute(text('SELECT count(*) FROM review_cases')).scalar_one()}; "
        )
        if case_id is not None:
            program += (
                f"p={{'case_id':{case_id!r}}}; "
                "r['decision_count']=c.execute(text('SELECT count(*) FROM decisions "
                "WHERE case_id=:case_id'),p).scalar_one(); "
                "r['decision_audit_count']=c.execute(text(\"SELECT count(*) FROM audit_events "
                "WHERE case_id=:case_id AND event_type='decision_recorded'\"),p).scalar_one(); "
            )
        program += "print(json.dumps(r)); c.close()"
        return json.loads(
            self.command(
                "database-counts", [*COMPOSE, "exec", "-T", "api", "python", "-c", program]
            )
        )

    def flows(self) -> dict[str, Any]:
        program = """
import json
from api.app.langflow_client import LangflowClient, flow_configuration, graph_hash
client=LangflowClient()
result={}
try:
    for kind in ('intake','report'):
        config=flow_configuration(kind)
        graph=client.get_flow(config['id'],config['flow_hash'])
        result[kind]={'id':config['id'],'flow_hash':graph_hash(graph),
                      'config_hash':config['config_hash']}
    print(json.dumps(result,sort_keys=True))
finally:
    client.close()
"""
        return json.loads(
            self.command(
                "published-flow-hashes", [*COMPOSE, "exec", "-T", "worker", "python", "-c", program]
            )
        )

    def recreate(self, original: dict[str, Any], overlay: Path | None) -> None:
        self.ensure_tag(original)
        compose = COMPOSE if overlay is None else [*COMPOSE, "-f", str(overlay)]
        self.command(
            "restore-langflow" if overlay is None else "inject-font-failure",
            [
                *compose,
                "up",
                "-d",
                "--no-deps",
                "--no-build",
                "--pull",
                "never",
                "--force-recreate",
                "langflow",
            ],
            timeout=90,
        )


def response(value: httpx.Response, expected: int = 200) -> Any:
    if value.status_code != expected:
        raise RuntimeError(f"Expected HTTP {expected}, observed {value.status_code}")
    return value.json()


def case(client: httpx.Client, identifier: str) -> dict[str, Any]:
    return response(client.get(f"/api/cases/{identifier}"))


def saved_detail(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        key: detail.get(key)
        for key in (
            "id",
            "status",
            "source_kind",
            "current_document_version_id",
            "assessment_id",
            "decision",
            "decision_id",
            "decision_reason",
            "decided_by",
            "reports",
            "jobs",
        )
    }


def wait_intake(client: httpx.Client, identifier: str, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 160
    while time.monotonic() < deadline:
        detail = case(client, identifier)
        job = next(item for item in detail["jobs"] if item["job_id"] == job_id)
        if job["state"] == "succeeded" and detail["status"] == "pending_approval":
            if not job["langflow_job_id"] or str(job["langflow_job_id"]).startswith("lf-demo"):
                raise AssertionError("A real Intake run ID is required")
            return detail
        if job["state"] == "failed":
            raise AssertionError("Synthetic Intake failed before report fault injection")
        time.sleep(1)
    raise TimeoutError("Synthetic Intake did not finish within 160 seconds")


def download(client: httpx.Client, identifier: str, artifact: dict[str, Any]) -> bytes:
    value = client.get(
        f"/api/cases/{identifier}/report/{artifact['format']}",
        params={"report_id": artifact["report_id"]},
    )
    value.raise_for_status()
    if digest(value.content) != artifact["sha256"] or len(value.content) != artifact["bytes"]:
        raise AssertionError("Downloaded bytes differ from the registered artifact")
    return value.content


def partial_failure(
    proof: Proof, client: httpx.Client, unique: str
) -> tuple[str, str, dict[str, Any]]:
    content = (
        "SYNTHETIC DEMO DOCUMENT\nBuilt on Langflow\n"
        f"仅PDF部分失败验收 {unique}\n供应方承担全部损失，且不设责任上限。\n"
    ).encode()
    accepted = response(
        client.post(
            "/api/cases",
            headers={"Idempotency-Key": f"report-font-upload-{unique}"},
            data={"title": "虚构PDF部分失败与专用重试验收", "synthetic_confirmed": "true"},
            files={"file": (f"report-font-{unique}.txt", content, "text/plain")},
        ),
        202,
    )
    identifier = accepted["case_id"]
    proof.result.update(case_id=identifier, source_sha256=digest(content), accepted=accepted)
    detail = wait_intake(client, identifier, accepted["job_id"])
    reason = "仅用虚构资料验证报告部分失败，人工决定应保留且现有报告不得被重写。"
    decided = response(
        client.post(
            f"/api/cases/{identifier}/decision",
            headers={
                "X-Reviewer": "synthetic-report-validator",
                "Idempotency-Key": f"report-font-decision-{unique}",
            },
            json={
                "decision": "changes_requested",
                "reason": reason,
                "document_version_id": detail["current_document_version_id"],
                "assessment_id": detail["assessment_id"],
                "expected_row_version": detail["row_version"],
            },
        )
    )
    jobs = [item for item in decided["jobs"] if item["kind"] == "report"]
    if len(jobs) != 1 or not decided["decision_id"]:
        raise AssertionError("Decision response must identify one bound report job")
    report_job = jobs[0]["job_id"]
    proof.result.update(decision_id=decided["decision_id"], report_job_id=report_job)
    first: dict[str, Any] | None = None
    deadline = time.monotonic() + 220
    while time.monotonic() < deadline:
        detail = case(client, identifier)
        job = next(item for item in detail["jobs"] if item["job_id"] == report_job)
        reports = {item["format"]: item for item in detail["reports"]}
        if first is None and {name: item["state"] for name, item in reports.items()} == {
            "json": "ready",
            "html": "ready",
            "pdf": "failed",
        }:
            if reports["pdf"]["error_code"] != "font_unavailable" or job["attempt"] != 1:
                raise AssertionError("First PDF-only failure was not observed in attempt one")
            first = saved_detail(detail)
            proof.save("first-partial.json", first)
            for name in ("json", "html"):
                proof.write(f"first-report.{name}", download(client, identifier, reports[name]))
        if detail["decision_id"] != decided["decision_id"] or detail["decision_reason"] != reason:
            raise AssertionError("Partial report failure changed the human decision")
        if job["state"] == "failed":
            if first is None or job["attempt"] != 3 or job["error_code"] != "report_partial":
                raise AssertionError("Expected exhausted three-attempt partial report failure")
            if not job["langflow_job_id"]:
                raise AssertionError("A real report Flow run ID is required")
            proof.save("terminal-failed.json", saved_detail(detail))
            return identifier, first["reports"][0]["snapshot_hash"], first
        if job["state"] == "succeeded":
            raise AssertionError("PDF unexpectedly succeeded while the invalid font was configured")
        time.sleep(0.5)
    raise TimeoutError("PDF failure did not exhaust automatic retries within 220 seconds")


def finish_retry(
    proof: Proof,
    client: httpx.Client,
    identifier: str,
    snapshot: str,
    first: dict[str, Any],
    unique: str,
) -> None:
    accepted = response(
        client.post(
            f"/api/cases/{identifier}/reports/retry",
            headers={"Idempotency-Key": f"report-font-retry-{unique}"},
            json={"snapshot_hash": snapshot, "formats": ["pdf"]},
        ),
        202,
    )
    proof.result["retry_job_id"] = accepted["job_id"]
    deadline = time.monotonic() + 160
    while time.monotonic() < deadline:
        detail = case(client, identifier)
        job = next(item for item in detail["jobs"] if item["job_id"] == accepted["job_id"])
        reports = {item["format"]: item for item in detail["reports"]}
        if (
            job["state"] == "succeeded"
            and len(reports) == 3
            and all(item["state"] == "ready" for item in reports.values())
        ):
            break
        if job["state"] == "failed":
            raise AssertionError("Failed-format manual retry did not recover PDF")
        time.sleep(1)
    else:
        raise TimeoutError("Failed-format manual retry did not finish within 160 seconds")
    if not job["langflow_job_id"] or job["retry_generation"] != 1:
        raise AssertionError("A new real report Flow in manual generation one is required")
    for key in (
        "decision_id",
        "decision",
        "decision_reason",
        "current_document_version_id",
        "assessment_id",
    ):
        if detail[key] != first[key]:
            raise AssertionError("Manual report retry changed the fixed decision/version")
    original = {item["format"]: item for item in first["reports"]}
    downloaded = []
    for name, artifact in reports.items():
        data = download(client, identifier, artifact)
        if name in {"json", "html"}:
            for key in ("report_id", "sha256", "bytes", "created_at", "snapshot_hash"):
                if artifact[key] != original[name][key]:
                    raise AssertionError("Ready artifact metadata was changed during PDF retry")
            if data != (proof.output / f"first-report.{name}").read_bytes():
                raise AssertionError("Ready report bytes were rewritten during PDF retry")
        else:
            proof.write("recovered-report.pdf", data)
        downloaded.append({"format": name, "sha256": digest(data), "bytes": len(data)})
    proof.save("final-report.json", saved_detail(detail))
    proof.result["downloaded"] = downloaded
    proof.result["ready_json_html_unchanged"] = True


def verify(proof: Proof) -> None:
    proof.result["git_head"] = proof.command("git-head", ["git", "rev-parse", "HEAD"])
    original = proof.container("langflow")
    environment = proof.environment(original)
    if "REVIEW_REPORT_FONT" in environment:
        raise RuntimeError(
            "Pre-existing REVIEW_REPORT_FONT is protected; this proof refuses to change it"
        )
    base_config = json.loads(
        proof.command("compose-config", [*COMPOSE, "config", "--format", "json"])
    )
    configured = base_config["services"]["langflow"]
    if configured["image"] != original["Config"]["Image"] or any(
        environment.get(key) != str(value)
        for key, value in configured.get("environment", {}).items()
    ):
        raise RuntimeError(
            "Base Compose env/image differs from the current container; restoration is unsafe"
        )
    proof.ensure_tag(original)
    if proof.identity(original)["health"] != "healthy":
        raise RuntimeError("Original Langflow must already be healthy")
    api_container = proof.container("api")
    binding = api_container["NetworkSettings"]["Ports"].get("8000/tcp", [])
    if not any(item["HostIp"] == "127.0.0.1" and item["HostPort"] == "8000" for item in binding):
        raise RuntimeError("The fixed API must be the isolated container's loopback binding")
    proof.container("worker")
    before_counts = proof.counts()
    if before_counts["active_jobs"]:
        raise RuntimeError("Wait for all other validations and active jobs to finish")
    before_flows = proof.flows()
    proof.result["before"] = {
        "langflow": proof.identity(original),
        "flows": before_flows,
        "counts": before_counts,
    }
    unique = uuid.uuid4().hex
    missing_font = f"/app/arc-proof-missing-font-{unique}.ttf"
    proof.command(
        "confirm-missing-font",
        [
            "docker",
            "exec",
            original["Id"],
            "python",
            "-c",
            f"from pathlib import Path; assert not Path({missing_font!r}).exists()",
        ],
    )
    overlay = proof.output / "font-fault.compose.json"
    proof.save(
        overlay.name,
        {"services": {"langflow": {"environment": {"REVIEW_REPORT_FONT": missing_font}}}},
    )
    with httpx.Client(base_url=API, timeout=20, follow_redirects=False, trust_env=False) as client:
        response(client.get("/api/health"))
        proof.result["restoration"] = {"required": True, "result": "pending"}
        try:
            proof.recreate(original, overlay)
            faulty = proof.health()
            if (
                faulty["Image"] != original["Image"]
                or proof.environment(faulty).get("REVIEW_REPORT_FONT") != missing_font
            ):
                raise AssertionError("Fault container image/env differs from the intended overlay")
            changed = proof.environment(faulty)
            changed.pop("REVIEW_REPORT_FONT")
            normal_identity = proof.identity(faulty)
            normal_identity.update(
                environment_sha256=digest(canonical(changed)), font_override_present=False
            )
            if changed != environment or normal_identity != proof.identity(original):
                raise AssertionError("Fault injection changed more than the font environment")
            identifier, snapshot, first = partial_failure(proof, client, unique)
        finally:
            proof.recreate(original, None)
            restored = proof.health()
            restored_flows = proof.flows()
            restoration = {"langflow": proof.identity(restored), "flows": restored_flows}
            proof.result["restoration"] = {"required": True, "result": "failed", **restoration}
            if (
                proof.identity(restored) != proof.identity(original)
                or restored_flows != before_flows
            ):
                raise AssertionError(
                    "Original Langflow image/env/mounts/Flow hashes were not restored"
                )
            proof.result["restoration"]["result"] = "passed"
            proof.save("restoration.json", proof.result["restoration"])
        finish_retry(proof, client, identifier, snapshot, first, unique)
        counts = proof.counts(identifier)
        if (
            counts["case_count"] != before_counts["case_count"] + 1
            or counts["active_jobs"]
            or counts["decision_count"] != 1
            or counts["decision_audit_count"] != 1
        ):
            raise AssertionError(
                "Expected one new case, one decision/audit and no remaining active jobs"
            )
        proof.result["after_counts"] = counts
        proof.result["result"] = "passed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    roots = (Path(tempfile.gettempdir()).resolve(), Path("/private/tmp").resolve())
    if (
        args.output.is_symlink()
        or not output.is_dir()
        or any(output.iterdir())
        or not any(output != root and output.is_relative_to(root) for root in roots)
    ):
        raise ValueError("Use a new empty existing system temporary directory")
    proof = Proof(output)

    def interrupted(_signum: int, _frame: object) -> None:
        raise InterruptedError("Report-retry proof interrupted; restore the original service")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        verify(proof)
    except BaseException as exc:
        proof.result["error"] = {"type": type(exc).__name__, "detail": str(exc)}
        raise
    finally:
        proof.result["ended_at"] = now()
        proof.result["commands"] = proof.records
        proof.result["files"] = [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}
            for path in sorted(output.iterdir())
            if path.is_file()
        ]
        proof.save("report-retry.json", proof.result)
    print(
        json.dumps({"result": "passed", "manifest": str(output / "report-retry.json")}), flush=True
    )


if __name__ == "__main__":
    main()
