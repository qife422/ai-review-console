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


def test_build_tools_scope_is_exact_original_subset():
    baseline = lock.baseline_pins(lock.BASELINE)
    build = lock.scoped_pins(baseline, "build-tools")
    assert build == lock.read_pins(lock.BUILD_PINS)
    assert set(build) == {"pip", "setuptools", "wheel", "packaging"}
    assert len(lock.scoped_pins(baseline, "runtime")) == 334
    baseline.pop("wheel")
    with pytest.raises(ValueError, match="four tools"):
        lock.scoped_pins(baseline, "build-tools")


def test_build_tools_scope_rejects_sdist():
    data = report()
    data["install"][0]["download_info"]["url"] = (
        "https://files.pythonhosted.org/packages/ab/example.tar.gz"
    )
    with pytest.raises(ValueError, match="wheel archives"):
        lock.lock_from_report(data, {"example-package": "1.2"}, wheel_only=True)


def make_report(pins):
    data = report()
    data["install"] = []
    for name, version in pins.items():
        item = copy.deepcopy(report()["install"][0])
        item["metadata"] = {"name": name, "version": version}
        data["install"].append(item)
    return data


@pytest.mark.parametrize("arch", ["amd64", "arm64"])
def test_build_tools_generate_and_verify_cli(tmp_path, monkeypatch, arch):
    import json
    import sys

    pins = lock.read_pins(lock.BUILD_PINS)
    source = tmp_path / "report.json"
    report_data = make_report(pins)
    report_data["environment"]["platform_machine"] = lock.ARCH_MACHINES[arch]
    source.write_text(json.dumps(report_data))
    output, receipt = tmp_path / "build.lock", tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lock",
            "generate",
            "--scope",
            "build-tools",
            "--arch",
            arch,
            "--report",
            str(source),
            "--lock",
            str(output),
            "--receipt",
            str(receipt),
        ],
    )
    lock.main()
    data = json.loads(receipt.read_text())
    assert data["dependency_scope"] == "build-tools"
    assert data["arch"] == arch
    assert lock.ARCH_MACHINES[arch] in output.read_text().splitlines()[0]
    assert data["package_count"] == 4
    assert data["sdist_count"] == 0
    assert len(output.read_text().splitlines()) == 5
    installed = {
        "environment": report_data["environment"],
        "packages": [{"name": name, "version": version} for name, version in pins.items()],
    }
    verification = tmp_path / "verified.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lock",
            "verify",
            "--scope",
            "build-tools",
            "--arch",
            arch,
            "--python",
            "/venv/bin/python",
            "--receipt",
            str(verification),
        ],
    )
    with patch.object(
        lock.subprocess,
        "run",
        side_effect=[
            Mock(),
            Mock(stdout=json.dumps(installed)),
        ],
    ):
        lock.main()
    result = json.loads(verification.read_text())
    assert result["arch"] == arch
    assert result["package_count"] == 4
    assert result["installed_set_matches_pins"] is True


def test_runtime_receipt_records_limited_sdist_build_policy(tmp_path, monkeypatch):
    import json
    import sys

    data = make_report(lock.read_pins(lock.PINS))
    data["install"][0]["download_info"]["url"] = (
        "https://files.pythonhosted.org/packages/ab/example.tar.gz"
    )
    source = tmp_path / "report.json"
    source.write_text(json.dumps(data))
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "lock",
            "generate",
            "--report",
            str(source),
            "--lock",
            str(tmp_path / "runtime.lock"),
            "--receipt",
            str(receipt),
        ],
    )
    lock.main()
    result = json.loads(receipt.read_text())
    assert result["package_count"] == 334
    assert result["sdist_count"] == 1
    policy = result["source_build_policy"]
    assert policy["build_tools"] == lock.read_pins(lock.BUILD_PINS)
    assert policy["binary_reproducibility_verified"] is False
    assert policy["policy_execution_verified_by_this_receipt"] is False


@pytest.mark.parametrize("arch,machine", [("amd64", "aarch64"), ("arm64", "x86_64")])
def test_report_rejects_cross_architecture(arch, machine):
    data = report()
    data["environment"]["platform_machine"] = machine
    with pytest.raises(ValueError, match=f"\\({arch}\\)"):
        lock.lock_from_report(data, {"example-package": "1.2"}, arch=arch)


@pytest.mark.parametrize("arch,machine", [("amd64", "aarch64"), ("arm64", "x86_64")])
def test_verify_rejects_cross_architecture(arch, machine):
    import json

    data = {
        "environment": dict(ENV, platform_machine=machine),
        "packages": [{"name": "example-package", "version": "1.2"}],
    }
    with (
        patch.object(lock.subprocess, "run", side_effect=[Mock(), Mock(stdout=json.dumps(data))]),
        pytest.raises(ValueError, match=f"\\({arch}\\)"),
    ):
        lock.verify_python("/venv/bin/python", {"example-package": "1.2"}, arch=arch)


def test_default_amd64_lock_bytes_remain_compatible():
    text, _ = lock.lock_from_report(report(), {"example-package": "1.2"})
    assert text == (
        "# Candidate CPython 3.12.16 Linux x86_64; install with --require-hashes\n"
        "example-package==1.2 --hash=sha256:" + "a" * 64 + "\n"
    )
    assert text == lock.lock_from_report(report(), {"example-package": "1.2"}, arch="amd64")[0]


@pytest.mark.parametrize("change", [{"python_full_version": "3.12.15"}, {"sys_platform": "darwin"}])
def test_arm64_rejects_wrong_python_or_os(change):
    data = report()
    data["environment"].update(platform_machine="aarch64", **change)
    with pytest.raises(ValueError, match="requires CPython"):
        lock.lock_from_report(data, {"example-package": "1.2"}, arch="arm64")


def test_arm64_still_requires_complete_exact_package_graph():
    data = report()
    data["environment"]["platform_machine"] = "aarch64"
    with pytest.raises(ValueError, match="complete baseline"):
        lock.lock_from_report(data, {"example-package": "1.2", "missing": "1"}, arch="arm64")
    data["install"][0]["metadata"]["version"] = "1.1"
    with pytest.raises(ValueError, match="unexpected resolved package"):
        lock.lock_from_report(data, {"example-package": "1.2"}, arch="arm64")
