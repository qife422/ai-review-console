from pathlib import Path

import pytest

from scripts.apply_system_updates import Recorder, check_os, manager_args, repositories


def repo_text(component: str, **changes: str) -> str:
    values = {
        "enabled": "1",
        "baseurl": "https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi10/10/"
        "$basearch/" + component + "/os",
        "gpgcheck": "1",
        "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
    } | changes
    return f"[ubi-10-{component}-rpms]\n" + "\n".join(f"{k}={v}" for k, v in values.items())


def write_repos(tmp_path: Path, **changes: str) -> Path:
    path = tmp_path / "ubi.repo"
    path.write_text(repo_text("baseos", **changes) + "\n" + repo_text("appstream"))
    return path


def test_accepts_existing_rhel10_and_rejects_other_distributions():
    assert check_os('ID="rhel"\nVERSION_ID="10.2"')["VERSION_ID"] == "10.2"
    for raw in ['ID=rhel\nVERSION_ID="9.7"', 'ID=fedora\nVERSION_ID="10"']:
        with pytest.raises(ValueError, match="RHEL10"):
            check_os(raw)


def test_only_explicit_default_ubi_repositories_are_used(tmp_path):
    path = write_repos(tmp_path)
    path.write_text(path.read_text() + "\n[paid-rhel]\nenabled=1\nbaseurl=https://example.org")
    result = repositories([path])
    assert len(result) == 2
    args = manager_args(result)
    assert "--disablerepo=*" in args
    assert "--setopt=gpgcheck=1" in args
    assert "--setopt=sslverify=1" in args
    assert not any("paid-rhel" in value for value in args)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "baseurl": "https://cdn-ubi.redhat.com.evil.org/content/public/ubi/dist/ubi10/10/x86_64/baseos/os"
        },
        {"baseurl": "http://cdn-ubi.redhat.com/content/public/ubi/dist/ubi10/10/x86_64/baseos/os"},
        {"baseurl": "https://cdn-ubi.redhat.com/content/public/ubi/dist/ubi9/9/x86_64/baseos/os"},
        {"gpgcheck": "0"},
        {"sslverify": "0"},
        {"gpgkey": "https://example.org/key"},
        {"mirrorlist": "https://example.org/mirrors"},
    ],
)
def test_rejects_origin_or_signature_policy_change(tmp_path, changes):
    with pytest.raises(ValueError, match="policy mismatch"):
        repositories([write_repos(tmp_path, **changes)])


def test_requires_both_enabled_default_ubi_repositories(tmp_path):
    with pytest.raises(ValueError, match="Both default"):
        repositories([write_repos(tmp_path, enabled="0")])


def test_refuses_duplicate_or_symlink_repo_configs(tmp_path):
    path = write_repos(tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        repositories([path, path])
    link = tmp_path / "link.repo"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="Unexpected"):
        repositories([link])


def test_captures_exact_output_and_fails_nonzero_without_replacement(tmp_path):
    recorder = Recorder(tmp_path / "records")
    assert recorder.run("ok", ["/usr/bin/printf", "actual output"]) == "actual output"
    with pytest.raises(RuntimeError, match="exit=7"):
        recorder.run("fail", ["/bin/sh", "-c", "printf failure >&2; exit 7"])
    assert recorder.commands[-1]["exit_code"] == 7
    assert (recorder.root / "fail.stderr").read_text() == "failure"
    with pytest.raises(ValueError, match="Never replace"):
        Recorder(recorder.root)


def test_fast_process_cannot_bypass_output_budget(tmp_path, monkeypatch):
    import scripts.apply_system_updates as module

    monkeypatch.setattr(module, "LIMIT", 8)
    recorder = Recorder(tmp_path / "records")
    with pytest.raises(RuntimeError, match="output_capacity"):
        recorder.run("too-large", ["/usr/bin/printf", "larger than budget"])
    assert recorder.commands[-1]["stop_reason"] == "output_capacity"
