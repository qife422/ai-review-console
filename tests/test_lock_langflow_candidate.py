"""Resolver/installed-set boundary tests; no network or container writes."""

import copy
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "candidate_lock", Path(__file__).parents[1] / "scripts/lock_langflow_candidate.py"
)
lock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lock)

ENV = {
    "python_full_version": "3.12.16",
    "sys_platform": "linux",
    "platform_machine": "x86_64",
    "implementation_name": "cpython",
}


def report():
    return {
        "version": "1",
        "environment": dict(ENV),
        "install": [
            {
                "metadata": {"name": "Example_Package", "version": "1.2"},
                "download_info": {
                    "url": "https://files.pythonhosted.org/packages/ab/example.whl",
                    "archive_info": {"hashes": {"sha256": "a" * 64}},
                },
            }
        ],
    }


def test_fixed_334_pins_match_original_inventory():
    assert lock.read_pins(lock.PINS) == lock.baseline_pins(lock.BASELINE)
    assert len(lock.read_pins(lock.PINS)) == 334


def test_complete_resolve_has_hash_and_source_kind():
    data = report()
    text, archives = lock.lock_from_report(data, {"example-package": "1.2"})
    assert "example-package==1.2 --hash=sha256:" + "a" * 64 in text
    assert archives[0]["kind"] == "wheel"
    data["install"][0]["download_info"]["url"] = (
        "https://files.pythonhosted.org/packages/ab/example.tar.gz"
    )
    assert lock.lock_from_report(data, {"example-package": "1.2"})[1][0]["kind"] == "sdist"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["environment"].update(platform_machine="aarch64"),
        lambda d: d["environment"].update(python_full_version="3.12.15"),
        lambda d: d["install"].append(copy.deepcopy(d["install"][0])),
        lambda d: d["install"][0]["metadata"].update(version="1.3"),
        lambda d: d["install"][0].update(is_direct=True),
        lambda d: d["install"][0].update(is_yanked=True),
        lambda d: d["install"][0]["download_info"]["archive_info"].update(hashes={}),
        lambda d: d["install"][0]["download_info"].update(
            url="https://evil.example/packages/x.whl"
        ),
        lambda d: d["install"][0]["download_info"].update(
            url="https://files.pythonhosted.org@evil.example/packages/x.whl"
        ),
        lambda d: d["install"][0]["download_info"].update(
            url="http://files.pythonhosted.org/packages/x.whl"
        ),
        lambda d: d["install"].clear(),
    ],
)
def test_resolver_rejects_untrusted_or_different_graph(mutation):
    data = report()
    mutation(data)
    with pytest.raises(ValueError):
        lock.lock_from_report(data, {"example-package": "1.2"})


@pytest.mark.parametrize(
    "line", ["Foo==1", "foo_bar==1", "foo>=1", "foo @ https://example.com/x.whl", "foo==1\nfoo==1"]
)
def test_pins_reject_noncanonical_unpinned_duplicate_or_url(tmp_path, line):
    path = tmp_path / "pins"
    path.write_text(line)
    with pytest.raises(ValueError):
        lock.read_pins(path)


def test_output_preflight_preserves_all_existing_bytes(tmp_path):
    existing, other = tmp_path / "old", tmp_path / "new"
    existing.write_bytes(b"preserved")
    with pytest.raises(ValueError):
        lock.write_outputs([(other, b"new"), (existing, b"changed")])
    assert existing.read_bytes() == b"preserved"
    assert not other.exists()
    with pytest.raises(ValueError):
        lock.write_outputs([(other, b"x" * (lock.MAX_OUTPUT + 1))])
    assert not other.exists()


def test_installed_set_requires_exact_versions_and_no_extra_packages():
    import json

    data = {"environment": ENV, "packages": [{"name": "example-package", "version": "1.2"}]}
    with patch.object(
        lock.subprocess, "run", side_effect=[Mock(), Mock(stdout=json.dumps(data))]
    ) as run:
        assert (
            lock.verify_python("/venv/bin/python", {"example-package": "1.2"})["pip_check"]
            == "passed"
        )
        assert run.call_args_list[0].args[0] == ["/venv/bin/python", "-m", "pip", "check"]
    data["packages"].append({"name": "extra", "version": "1"})
    with (
        patch.object(lock.subprocess, "run", side_effect=[Mock(), Mock(stdout=json.dumps(data))]),
        pytest.raises(ValueError, match="installed package set"),
    ):
        lock.verify_python("/venv/bin/python", {"example-package": "1.2"})
