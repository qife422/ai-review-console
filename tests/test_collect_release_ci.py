from collections import namedtuple
from pathlib import Path

import pytest

from scripts.collect_release_ci import Collector, identity


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
