import base64
import hashlib
import json
from collections import namedtuple
from pathlib import Path

import pytest

from scripts.collect_release_ci import (
    Collector,
    collect_native_for_profile,
    extract_system_records,
    identity,
)


def test_container_identity_requires_exact_current_project_service_and_full_digest() -> None:
    digest = "sha256:" + "a" * 64
    assert identity(digest + " arc-ci-123 api", "arc-ci-123", "api") == digest
    for raw in [
        digest + " ai-review-console-upgrade api",
        digest + " arc-ci-123 worker",
        "image:latest arc-ci-123 api",
        digest + " arc-ci-123 api extra",
    ]:
        with pytest.raises(ValueError):
            identity(raw, "arc-ci-123", "api")


def test_collector_stops_before_generation_when_disk_headroom_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    disk = namedtuple("disk", "total used free")
    monkeypatch.setattr(
        "scripts.collect_release_ci.shutil.disk_usage",
        lambda _: disk(10 * 1024**3, 9 * 1024**3, 1024**3),
    )
    target = tmp_path / "new"
    with pytest.raises(RuntimeError, match="6 GiB"):
        Collector(target, "arc-ci-123")
    assert not target.exists()


def test_collector_rejects_foreign_projects_and_existing_evidence(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="current arc-ci"):
        Collector(tmp_path / "new", "ai-review-console-upgrade")
    (tmp_path / "protected").write_text("original")
    with pytest.raises(ValueError, match="absent or empty"):
        Collector(tmp_path, "arc-ci-123")
    assert (tmp_path / "protected").read_text() == "original"


def system_export() -> dict:
    files = {
        name: b"recorded output\n"
        for name in ("rpm-before.stdout", "rpm-after.stdout", "update.stdout")
    }
    entries = [
        {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in files.items()
    ]
    files["manifest.json"] = json.dumps({"status": "completed", "files": entries}).encode()
    return {
        "files": [
            {
                "path": name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "base64": base64.b64encode(data).decode(),
            }
            for name, data in files.items()
        ]
    }


def test_system_export_rejects_path_escape_before_creating_output(tmp_path: Path) -> None:
    exported = system_export()
    exported["files"][0]["path"] = "../escape"
    target = tmp_path / "records"
    with pytest.raises(ValueError, match="record path"):
        extract_system_records(json.dumps(exported), target)
    assert not target.exists() and not (tmp_path / "escape").exists()


def test_system_export_rejects_changed_transport_bytes_before_writes(tmp_path: Path) -> None:
    exported = system_export()
    exported["files"][0]["base64"] = base64.b64encode(b"changed").decode()
    target = tmp_path / "records"
    with pytest.raises(ValueError, match="integrity mismatch"):
        extract_system_records(json.dumps(exported), target)
    assert not target.exists()


def test_system_export_checks_manifest_and_preserves_existing_output(tmp_path: Path) -> None:
    raw = json.dumps(system_export())
    target = tmp_path / "records"
    assert extract_system_records(raw, target)["status"] == "completed"
    original = (target / "rpm-after.stdout").read_bytes()
    with pytest.raises(ValueError, match="must not exist"):
        extract_system_records(raw, target)
    assert (target / "rpm-after.stdout").read_bytes() == original


@pytest.mark.parametrize("system,machine", [("Linux", "x86_64"), ("Darwin", "arm64")])
def test_native_skip_cannot_silently_apply_to_other_platforms(system: str, machine: str) -> None:
    with pytest.raises(ValueError, match="Linux ARM"):
        collect_native_for_profile("arm-backend", system, machine)


def test_native_profile_limits_the_arm_job_without_resetting_another_batch() -> None:
    assert collect_native_for_profile("complete", "Linux", "x86_64")
    assert not collect_native_for_profile("arm-backend", "Linux", "aarch64")


def test_os_identity_requires_exact_profile_and_debian_version() -> None:
    from scripts.collect_release_ci import verify_os_release

    assert verify_os_release('ID=debian\nVERSION_ID="12"\n', "debian")["version_id"] == "12"
    assert verify_os_release('ID="rhel"\nVERSION_ID="10.2"\n', "rhel")["id"] == "rhel"
    for raw, profile in [
        ("ID=debian\nVERSION_ID=11\n", "debian"),
        ("ID=rhel\nVERSION_ID=10\n", "debian"),
        ("ID=debian\nVERSION_ID=12\n", "rhel"),
        ("ID=debian\nID=rhel\nVERSION_ID=12\n", "debian"),
    ]:
        with pytest.raises(ValueError):
            verify_os_release(raw, profile)


def test_cli_profiles_require_identity_and_keep_primary_scans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from scripts import collect_release_ci as module

    class FakeCollector:
        def __init__(self, root, project):
            self.root = root
            self.root.mkdir()
            self.project = project
            self.commands = []

        def images(self):
            return {name: "sha256:" + "a" * 64 for name in ("api", "langflow", "web", "postgres")}

        def run(self, label, argv, **kwargs):
            self.commands.append({"label": label, "argv": argv})
            if label == "langflow-os-release":
                return 0, 'ID=debian\nVERSION_ID="12"\n'
            if label == "image-audit":
                (self.root / "images").mkdir()
                (self.root / "images/manifest.json").write_text("{}")
            return 0, ""

    monkeypatch.setattr(module, "Collector", FakeCollector)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collector",
            "--output-dir",
            str(tmp_path / "ok"),
            "--os-profile",
            "debian",
            "--native-profile",
            "prior-materials",
        ],
    )
    with pytest.raises(SystemExit) as status:
        module.main()
    assert status.value.code == 0
    manifest = json.loads((tmp_path / "ok/manifest.json").read_text())
    labels = [command["label"] for command in manifest["commands"]]
    probe = next(c for c in manifest["commands"] if c["label"] == "dependency-compatibility")
    assert "--candidate-1-13-1" in probe["argv"]
    assert "image-audit" in labels and "image-licenses" in labels
    assert "rhel-audit" not in labels and "system-materials" not in labels
    assert manifest["audits"]["redhat_supplement"]["state"] == "not_applicable"
    assert manifest["native_materials"]["state"] == "not_collected_this_image"
    assert manifest["native_materials"]["legal_approval"] is False
    assert "native-materials" not in labels
    assert any(
        item["path"].endswith("native-close/selection.json") for item in manifest["source_inputs"]
    )

    monkeypatch.setattr(sys, "argv", ["collector", "--output-dir", str(tmp_path / "mismatch")])
    with pytest.raises(SystemExit) as status:
        module.main()
    assert status.value.code == 1
    failed = json.loads((tmp_path / "mismatch/manifest.json").read_text())
    assert "OS profile mismatch" in failed["error"]
    assert [command["label"] for command in failed["commands"]] == ["langflow-os-release"]
