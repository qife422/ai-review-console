"""Boundary tests for license evidence collection; no Docker or network access."""

from __future__ import annotations

import argparse
import io
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_image_licenses as collector


@pytest.mark.parametrize(
    "value",
    [
        "api:latest",
        "api=latest",
        "other=sha256:" + "a" * 64,
        "api=sha256:" + "A" * 64,
        "web=sha256:abc",
    ],
)
def test_image_identity_rejects_tags_and_unapproved_aliases(value):
    with pytest.raises(argparse.ArgumentTypeError):
        collector.image_argument(value)


def test_exact_digest_is_accepted():
    assert collector.image_argument("api=sha256:" + "a" * 64) == ("api", "sha256:" + "a" * 64)


def test_nonempty_output_is_never_overwritten(tmp_path):
    existing = tmp_path / "sealed"
    existing.mkdir()
    fixed = existing / "manifest.json"
    fixed.write_text("fixed input")
    with pytest.raises(ValueError, match="never overwrite"):
        collector.prepare_output(existing)
    assert fixed.read_text() == "fixed input"


def test_output_symlink_is_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        collector.prepare_output(link)


def test_missing_license_and_symlink_escape_are_explicit(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    missing = collector.read_file(root / "LICENSE", root, collector.TextBudget())
    assert missing["reason"] == "missing_file" and missing["sha256"] is None
    outside = tmp_path / "private-LICENSE"
    outside.write_text("must not be exposed")
    link = root / "LICENSE"
    link.symlink_to(outside)
    escaped = collector.read_file(link, root, collector.TextBudget())
    assert escaped["reason"] == "resolved_path_outside_allowed_root"
    assert "text" not in escaped and escaped["sha256"] is None


def test_per_file_and_shared_limits_do_not_silently_truncate(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "MAX_FILE", 16)
    path = tmp_path / "LICENSE"
    path.write_bytes(b"x" * 17)
    result = collector.read_file(path, tmp_path, collector.TextBudget())
    assert result["reason"] == "per_file_limit" and "text" not in result
    path.write_bytes(b"abc")
    budget = collector.TextBudget(files=1, size=3)
    assert collector.read_file(path, tmp_path, budget)["state"] == "recorded"
    assert collector.read_file(path, tmp_path, budget)["reason"] == "batch_file_limit"
    assert budget.remaining() == {"files": 0, "bytes": 0}
    assert collector.read_file(path, tmp_path, collector.TextBudget(size=2))["reason"] == (
        "batch_byte_limit"
    )


def test_hash_only_font_does_not_consume_text_or_expose_bytes(tmp_path):
    path = tmp_path / "font.ttf"
    path.write_bytes(b"font fixture")
    budget = collector.TextBudget(files=0, size=0)
    result = collector.read_file(path, tmp_path, budget, text=False)
    assert result["state"] == "hashed_only"
    assert result["sha256"] == collector.digest(b"font fixture")
    assert "text" not in result
    assert budget.remaining() == {"files": 0, "bytes": 0}


def test_missing_release_license_is_not_approved(tmp_path, monkeypatch):
    distribution = SimpleNamespace(
        metadata={"Name": "zep-python", "License": None},
        version="2.0.2",
        files=[Path("zep_python/client.py")],
        locate_file=lambda p: tmp_path / p,
    )
    monkeypatch.setattr(collector.importlib.metadata, "distributions", lambda: [distribution])
    monkeypatch.setattr(collector, "PROJECT_FILES", ())
    monkeypatch.setattr(collector, "FONT_PATH", str(tmp_path / "absent-font"))
    report = collector.collect_python("langflow", collector.TextBudget())
    assert report["legal_approval"] is False
    package = report["selected_packages"][0]
    assert package["name"] == "zep-python" and package["version"] == "2.0.2"
    assert package["license_text_state"] == "no_license_text_recorded"
    assert package["missing_text_is_not_permission"] is True


def test_web_archive_symlinks_and_missing_text_are_explicit():
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        link = tarfile.TarInfo(collector.WEB_FILES[0])
        link.type = tarfile.SYMTYPE
        link.linkname = "/private/LICENSE"
        archive.addfile(link)
    report = collector.collect_web_archive(data.getvalue(), collector.TextBudget())
    assert report[0]["reason"] == "not_regular_file_or_symlink"
    assert report[1]["reason"] == "missing_file"
    assert all("text" not in item for item in report)


def test_write_json_preserves_existing_evidence(tmp_path):
    path = tmp_path / "api.json"
    first = collector.write_json(path, {"source": "first"})
    with pytest.raises(FileExistsError):
        collector.write_json(path, {"source": "replacement"})
    assert collector.digest(path.read_bytes()) == first["sha256"]


@pytest.mark.parametrize("with_text", [False, True])
def test_license_named_source_and_bytecode_are_not_legal_text(tmp_path, monkeypatch, with_text):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/license.py").write_text("raise RuntimeError('source, not a license')")
    (tmp_path / "pkg/license.pyc").write_bytes(b"\x00bytecode")
    files = [Path("pkg/license.py"), Path("pkg/license.pyc")]
    if with_text:
        (tmp_path / "pkg/LICENSE.txt").write_text("MIT license fixture")
        files.append(Path("pkg/LICENSE.txt"))
    distribution = SimpleNamespace(
        metadata={"Name": "litellm", "License": "MIT"},
        version="1.103.1",
        files=files,
        locate_file=lambda p: tmp_path / p,
    )
    monkeypatch.setattr(collector.importlib.metadata, "distributions", lambda: [distribution])
    monkeypatch.setattr(collector, "PROJECT_FILES", ())
    monkeypatch.setattr(collector, "FONT_PATH", str(tmp_path / "absent-font"))
    budget = collector.TextBudget(files=1)
    report = collector.collect_python("langflow", budget)["selected_packages"][0]
    assert report["license_text_state"] == ("recorded" if with_text else "no_license_text_recorded")
    excluded = [r for r in report["license_files"] if r["state"] == "excluded"]
    assert len(excluded) == 2 and all("text" not in r for r in excluded)
    assert budget.files_left == (0 if with_text else 1)
