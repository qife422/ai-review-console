"""Fault proof selectors must fail before mutating a foreign runtime."""

import sys
from pathlib import Path

import pytest

from scripts import candidate_runtime_guard as guard
from scripts import verify_faults, verify_report_retry


@pytest.fixture(autouse=True)
def run_identity(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")


@pytest.mark.parametrize(
    "project,version",
    [
        ("ai-review-console", "1.13.1"),
        ("arc-ci-999-amd64", "1.13.1"),
        ("arc-ci-12345-amd64", "1.11.6"),
        ("arc-ci-12345-amd64-evil", "1.13.1"),
        ("ai-review-console-upgrade", "1.13.1"),
    ],
)
def test_foreign_or_wrong_version_selectors_fail(project, version):
    with pytest.raises(ValueError):
        guard.CandidateRuntimeGuard(project, Path("docker-compose.yml"), version)


def test_ci_gate_rejects_legacy_in_ci_and_locally(monkeypatch):
    with pytest.raises(ValueError):
        guard.require_candidate_namespace("ai-review-console-upgrade", "1.11.6")
    guard.require_candidate_namespace("arc-ci-12345-amd64", "1.13.1")
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError):
        guard.require_candidate_namespace("ai-review-console-upgrade", "1.11.6")
    with pytest.raises(ValueError):
        guard.require_candidate_namespace("arc-ci-12345-amd64", "1.13.1")


def test_guard_requires_actual_observed_version_before_returning(monkeypatch):
    target = guard.CandidateRuntimeGuard("arc-ci-12345-amd64", Path("unused"), "1.13.1")
    monkeypatch.setattr(target, "check", lambda: None)
    monkeypatch.setattr(target, "bind_runtime", lambda _: None)
    monkeypatch.setattr(target, "verify_effective_worker", lambda: None)

    class Client:
        def request(self, *args):
            class Response:
                def json(self):
                    return {"info": {"version": "1.11.6"}}

            return Response()

        def close(self):
            pass

    monkeypatch.setattr(guard, "LangflowClient", Client)
    with pytest.raises(AssertionError, match="expected Langflow 1.13.1"):
        target.validate()


def test_database_binding_must_match_target_published_port(monkeypatch):
    target = guard.CandidateRuntimeGuard(
        "arc-ci-12345-amd64", Path("unused"), "1.13.1", database_port=5433
    )
    target.running = {
        "postgres": {
            "NetworkSettings": {
                "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "15433"}]}
            }
        }
    }
    monkeypatch.setattr(target, "check", lambda: None)
    monkeypatch.setattr(target, "bind_runtime", lambda _: None)
    monkeypatch.setattr(target, "verify_effective_worker", lambda: None)
    with pytest.raises(ValueError, match="Database loopback port"):
        target.validate()


@pytest.mark.parametrize("attack", ["project", "service", "image", "mount"])
def test_one_shot_kill_rechecks_actual_identity_and_mounts(monkeypatch, attack):
    target = guard.CandidateRuntimeGuard("arc-ci-12345-amd64", Path("unused"), "1.13.1")
    item = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": target.project,
                "com.docker.compose.service": "worker",
            }
        },
        "Image": "sha256:owned",
        "Mounts": [],
    }
    target.running["worker"] = {"Image": "sha256:owned", "Mounts": []}
    if attack == "project":
        item["Config"]["Labels"]["com.docker.compose.project"] = "original"
    elif attack == "service":
        item["Config"]["Labels"]["com.docker.compose.service"] = "postgres"
    elif attack == "image":
        item["Image"] = "sha256:other"
    else:
        item["Mounts"] = [
            {"Type": "volume", "Name": "original", "Destination": "/app/documents", "RW": False}
        ]
    monkeypatch.setattr(target, "inspect", lambda *a: item)
    with pytest.raises(ValueError):
        target.assert_container("new-one-shot", "worker")


@pytest.mark.parametrize("module", [verify_faults, verify_report_retry])
def test_both_cli_guards_run_before_mutating_commands(monkeypatch, tmp_path, module):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "proof",
            "--output",
            str(tmp_path),
            "--project",
            "arc-ci-12345-amd64",
            "--expected-langflow-version",
            "1.13.1",
        ],
    )

    class Reject:
        def __init__(self, *a, **kw):
            pass

        def validate(self):
            raise ValueError("deliberate target rejection")

    monkeypatch.setattr(module, "CandidateRuntimeGuard", Reject)
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **k: pytest.fail("No process mutation")
    )
    with pytest.raises(ValueError, match="target rejection"):
        module.main()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("attack", [None, "image", "env", "mount", "network", "alias"])
def test_effective_worker_is_checked_before_compose_run(monkeypatch, attack):
    import json

    target = guard.CandidateRuntimeGuard("arc-ci-12345-amd64", Path("unused"), "1.13.1")
    image = {
        "Id": "sha256:owned",
        "Config": {"Env": ["PATH=/bin"], "User": "10001", "Entrypoint": None, "Cmd": ["default"]},
    }
    service = {
        "image": "image:owned",
        "environment": {"DATABASE_URL": "target"},
        "command": ["python", "-m", "api.app.worker"],
        "volumes": [{"source": "documents", "target": "/app/documents", "read_only": True}],
        "networks": {"backend": {}},
    }
    config = {
        "services": {"worker": service},
        "volumes": {"documents": {"name": "owned_documents"}},
        "networks": {"backend": {"name": "owned_backend"}},
    }
    target.running["worker"] = {
        "Image": "sha256:owned",
        "Config": {
            "Image": "image:owned",
            "Env": ["PATH=/bin", "DATABASE_URL=target"],
            "Cmd": service["command"],
            "Entrypoint": None,
            "User": "10001",
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": "owned_documents",
                "Destination": "/app/documents",
                "RW": False,
            }
        ],
        "NetworkSettings": {"Networks": {"owned_backend": {}}},
    }
    if attack == "image":
        service["image"] = "other-image"
    elif attack == "env":
        service["environment"]["DATABASE_URL"] = "original"
    elif attack == "mount":
        config["volumes"]["documents"]["name"] = "original_documents"
    elif attack == "network":
        config["networks"]["backend"]["name"] = "original_backend"
    elif attack == "alias":
        service["networks"]["backend"]["aliases"] = ["postgres"]
    monkeypatch.setattr(target, "run", lambda *a, **k: json.dumps(config).encode())
    monkeypatch.setattr(target, "inspect", lambda *a: image)
    if attack:
        with pytest.raises(ValueError):
            target.verify_effective_worker()
    else:
        target.verify_effective_worker()


def test_one_shot_preflight_rejects_before_start(monkeypatch):
    class Reject:
        def verify_effective_worker(self):
            raise ValueError("effective worker mismatch")

    monkeypatch.setattr(verify_faults, "GUARD", Reject())
    monkeypatch.setattr(
        verify_faults, "command", lambda *a, **k: pytest.fail("Must not start process")
    )
    with pytest.raises(ValueError, match="worker mismatch"):
        verify_faults.one_shot("fakejob", "before_execution", [])


@pytest.mark.parametrize("primary_failure", [True, False])
def test_fault_manifest_survives_worker_restoration_failure(monkeypatch, tmp_path, primary_failure):
    import json

    class Guard:
        compose = ["docker", "compose", "-p", "arc-ci-12345-amd64"]
        running = {"worker": {"Id": "owned-worker"}}

        def __init__(self, *a, **kw):
            pass

        def validate(self):
            pass

        def assert_container(self, *a):
            pass

        def verify_effective_worker(self):
            pass

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, *a):
            return self

        def fetchone(self):
            return (0,)

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, *a):
            return self

        def raise_for_status(self):
            return self

        def json(self):
            return {"status": "ok"}

    def verify(*a):
        if primary_failure:
            raise RuntimeError("original primary failure")
        return {"result": "passed"}

    def failed_restore(*a, **kw):
        raise RuntimeError("restoration failed")

    monkeypatch.setattr(verify_faults, "CandidateRuntimeGuard", Guard)
    monkeypatch.setattr(verify_faults, "database", lambda: Connection())
    monkeypatch.setattr(verify_faults.httpx, "Client", Client)
    monkeypatch.setattr(verify_faults, "verify", verify)
    monkeypatch.setattr(verify_faults, "command", failed_restore)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "proof",
            "--output",
            str(tmp_path),
            "--project",
            "arc-ci-12345-amd64",
            "--expected-langflow-version",
            "1.13.1",
            "--mode",
            "before_execution",
        ],
    )
    with pytest.raises(
        RuntimeError, match="original primary" if primary_failure else "Worker restoration"
    ):
        verify_faults.main()
    manifest = json.loads((tmp_path / "faults.json").read_bytes())
    assert manifest["result"] == "failed" and manifest["restoration"]["result"] == "failed"
    assert ("original primary failure" in manifest.get("failure", "")) == primary_failure
