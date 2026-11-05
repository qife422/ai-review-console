"""Read-only validation of the isolated migration execution entrypoint."""

import re
import subprocess
from pathlib import Path

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
    assert len(paths) == 9
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
