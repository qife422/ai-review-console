import base64
import hashlib
import json
from collections import namedtuple
from pathlib import Path

import pytest

from scripts.collect_release_ci import Collector, extract_system_records, identity


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
