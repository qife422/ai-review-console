"""Read-only validation of the isolated migration execution entrypoint."""

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker/compose.migration.yml"
WORKFLOW = ROOT / ".github/workflows/langflow-migration.yml"


def workflow():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["migration"]


def test_compose_cannot_mount_original_databases_or_host_data():
    config = yaml.safe_load(COMPOSE.read_text())
    assert set(config["volumes"]) == {
        "postgres-data",
        "source-documents",
        "report-artifacts",
        "flow-config",
    }
    assert not any(config["volumes"].values())
    mounts = [
        mount for service in config["services"].values() for mount in service.get("volumes", [])
    ]
    binds = [mount for mount in mounts if mount.startswith(".") or mount.startswith("/")]
    assert binds == ["./postgres-init.sql:/docker-entrypoint-initdb.d/01-databases.sql:ro"]
    assert all("build" not in service for service in config["services"].values())
    assert config["services"]["storage-init"]["network_mode"] == "none"
    for name in ("langflow", "api", "web"):
        assert all(port.startswith("127.0.0.1:") for port in config["services"][name]["ports"])


def test_workflow_shell_and_embedded_python_compile_without_execution():
    for step in workflow()["steps"]:
        shell = step.get("run")
        if not shell:
            continue
        subprocess.run(["bash", "-n"], input=shell, text=True, check=True, capture_output=True)
        for index, code in enumerate(re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", shell, re.S)):
            compile(code, f"{step['name']}:python-{index}", "exec")


def test_restore_stages_do_not_bootstrap_or_migrate_application():
    steps = workflow()["steps"]
    restore_steps = [step for step in steps if step.get("name", "").startswith("Restore the")]
    assert len(restore_steps) == 2
    for step in restore_steps:
        commands = "\n".join(
            line for line in step["run"].splitlines() if not line.lstrip().startswith("#")
        )
        assert "run -T --no-deps migrate" not in commands
        assert "run -T --no-deps flow-init" not in commands
        assert "bootstrap_langflow.py" not in commands
        assert commands.index("arc_migration_require_absent") < commands.index("up -d")
        assert commands.index("arc_migration_verify restore") < commands.index("900 langflow")
        assert "arc_migration_verify verify" in commands


def test_artifact_upload_is_an_exact_bounded_selection():
    steps = workflow()["steps"]
    upload = next(
        step for step in steps if step.get("uses", "").startswith("actions/upload-artifact")
    )
    paths = upload["with"]["path"].splitlines()
    assert len(paths) == 10
    assert any(path.endswith("/architecture.json") for path in paths)
    assert all(
        "*" not in path and "checkpoint/" not in path and not path.endswith(".sql")
        for path in paths
    )
    assert "steps.evidence_manifest.outcome == 'success'" in upload["if"]
    manifest = next(step for step in steps if step.get("id") == "evidence_manifest")
    assert "1048576" in manifest["run"] and "262144" in manifest["run"]


def test_workflow_has_no_destructive_docker_commands():
    text = WORKFLOW.read_text()
    assert not re.search(r"\b(?:down|prune)\b|--rm\b|docker\s+(?:rm|volume\s+rm)\b", text)
    entry = workflow()["steps"][1]["run"]
    assert "32212254720" in entry
    assert "5368709120" in entry
    assert "for phase in baseline upgrade rollback" in entry


def test_platform_gate_precedes_baseline_and_records_platform_locks():
    steps = workflow()["steps"]
    gate = next(
        i for i, step in enumerate(steps) if step.get("name", "").startswith("Verify native Docker")
    )
    baseline = next(
        i
        for i, step in enumerate(steps)
        if step.get("name", "").startswith("Create only the fresh baseline")
    )
    assert gate < baseline
    manifest = next(step["run"] for step in steps if step.get("id") == "evidence_manifest")
    assert "selected_platform_locks" in manifest and "candidate-build-tools-arm64.lock" in manifest
    assert "Mac host" in manifest and "zero loss of post-checkpoint writes" in manifest


@pytest.mark.parametrize("failure", [None, "architecture", "os", "id", "count"])
def test_platform_evidence_accepts_only_matching_immutable_images(tmp_path, monkeypatch, failure):
    gate = next(
        step
        for step in workflow()["steps"]
        if step.get("name", "").startswith("Verify native Docker")
    )
    code = re.search(r"<<'PY'\n(.*?)\nPY(?:\n|$)", gate["run"], re.S).group(1)
    meta = tmp_path / "meta"
    meta.mkdir()
    rows = [f"sha256:{i:064x} linux arm64" for i in range(1, 6)]
    if failure == "architecture":
        rows[2] = rows[2].replace("arm64", "amd64")
    elif failure == "os":
        rows[2] = rows[2].replace("linux", "windows")
    elif failure == "id":
        rows[2] = "sha256:bad linux arm64"
    elif failure == "count":
        rows.pop()
    (tmp_path / "image-platforms.txt").write_text("\n".join(rows) + "\n")
    for key, value in {
        "ARC_MIGRATION_ROOT": str(tmp_path),
        "ARC_MIGRATION_META": str(meta),
        "ARC_MIGRATION_ARCH": "arm64",
        "ARC_MIGRATION_RUNNER_ARCH": "ARM64",
        "ARC_MIGRATION_DOCKER_PLATFORM": "linux aarch64",
        "ARC_MIGRATION_POSTGRES_IMAGE": "postgres:pin",
    }.items():
        monkeypatch.setenv(key, value)
    if failure:
        with pytest.raises(SystemExit):
            exec(compile(code, "platform-evidence", "exec"), {})
        assert not (meta / "architecture.json").exists()
    else:
        exec(compile(code, "platform-evidence", "exec"), {})
        evidence = json.loads((meta / "architecture.json").read_text())
        assert evidence["requested"] == "arm64" and evidence["runner_arch"] == "ARM64"
        assert set(evidence["images"]) == {"baseline", "candidate", "api", "web", "postgres"}
        assert all(
            item["os"] == "linux" and item["architecture"] == "arm64"
            for item in evidence["images"].values()
        )
        assert [item["image_id"] for item in evidence["images"].values()] == [
            row.split()[0] for row in rows
        ]
