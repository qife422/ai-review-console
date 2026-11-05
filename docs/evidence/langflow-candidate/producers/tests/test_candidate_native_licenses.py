import ast
import hashlib
import stat
from pathlib import Path, PurePosixPath

from scripts.verify_langflow_candidate import PRODUCER


def collector():
    tree = ast.parse(PRODUCER)
    function = next(n for n in tree.body if getattr(n, "name", None) == "collect_native_notices")
    environment = {"Path": Path, "stat": stat, "hashlib": hashlib}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "candidate-license-producer", "exec"),
        environment,
    )
    return environment["collect_native_notices"]


class Distribution:
    version = "fixture"

    def __init__(self, root, names):
        self.root = root
        self.files = [PurePosixPath(n) for n in names]

    def locate_file(self, name):
        return self.root / name


def test_default_does_not_read_target_license_metadata():
    class NoReads:
        @property
        def files(self):
            raise AssertionError("No targeted file selection when not requested")

    result = collector()({"apsw": NoReads()}, False)
    assert result["read_files"] == result["input_bytes"] == 0
    assert result["state"] == "not_requested"


def test_declared_specimens_have_exact_bytes_and_exclude_binary(tmp_path):
    (tmp_path / "LICENSE").write_bytes(b"Exact license specimen\n")
    (tmp_path / "libsqlite.so").write_bytes(b"never read")
    dist = Distribution(tmp_path, ["LICENSE", "libsqlite.so"])
    result = collector()({"apsw": dist}, True)
    assert result["read_files"] == 1
    item = next(r for r in result["files"] if r.get("state") == "recorded")
    assert item["text"].encode() == b"Exact license specimen\n"
    assert item["sha256"] == hashlib.sha256(item["text"].encode()).hexdigest()
    assert result["legal_approval"] is False


def test_symlink_escape_is_excluded_before_read(tmp_path):
    root = tmp_path / "distribution"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private fixture")
    (root / "LICENSE").symlink_to(outside)
    result = collector()({"apsw": Distribution(root, ["LICENSE"])}, True)
    assert result["read_files"] == result["input_bytes"] == 0
    assert result["files"][1]["state"] == "excluded_outside_distribution_root"


def test_oversized_specimen_is_not_opened(tmp_path, monkeypatch):
    (tmp_path / "LICENSE").write_bytes(b"x" * 262145)
    dist = Distribution(tmp_path, ["LICENSE"])

    def reject_open(*args, **kwargs):
        raise AssertionError("Oversized file must be rejected before reading")

    monkeypatch.setattr(Path, "open", reject_open)
    result = collector()({"apsw": dist}, True)
    assert result["read_files"] == result["input_bytes"] == 0
    assert result["files"][1]["state"] == "not_read_budget_limit"
