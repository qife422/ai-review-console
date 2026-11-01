import argparse
from pathlib import Path

import pytest

from scripts.scan_images_osv import Output, batch_queries, query_for, validate_image


def test_distribution_mapping_uses_source_and_epoch_not_binary_version() -> None:
    package = {
        "name": "libssl3t64",
        "version": "3.5.1-1+b2",
        "type": "deb",
        "source_name": "openssl",
        "source_version": "3.5.1-1",
    }
    query = query_for(package, {"ID": "debian", "VERSION_ID": "13"})
    assert query == {"package": {"name": "openssl", "ecosystem": "Debian:13"}, "version": "3.5.1-1"}
    package.update(source_name="krb5", source_version="1:1.21.3-5")
    assert query_for(package, {"ID": "debian", "VERSION_ID": "12"})["version"] == "1:1.21.3-5"
    assert query_for(package, {"ID": "ubuntu", "VERSION_ID": "24.04"}) is None
    assert query_for({"name": "x", "type": "rpm", "version": "1"}, {}) is None


def test_alpine_origin_and_python_normalization() -> None:
    assert query_for(
        {"type": "apk", "name": "libcrypto3", "source_name": "openssl", "version": "3.5.4-r0"},
        {"ID": "alpine", "VERSION_ID": "3.22.2"},
    ) == {"package": {"ecosystem": "Alpine:v3.22", "name": "openssl"}, "version": "3.5.4-r0"}
    assert query_for({"type": "pypi", "name": "zope.Interface", "version": "8"}, {}) == {
        "package": {"ecosystem": "PyPI", "name": "zope-interface"},
        "version": "8",
    }


def test_batch_paginates_only_pending_queries_and_does_not_drop_first_page() -> None:
    calls = []

    def request(url, payload):
        calls.append(payload)
        if len(calls) == 1:
            return {"results": [{"vulns": [{"id": "CVE-first"}], "next_page_token": "next"}, {}]}
        assert len(payload["queries"]) == 1
        assert payload["queries"][0]["page_token"] == "next"
        return {"results": [{"vulns": [{"id": "CVE-last"}]}]}

    queries = [
        {"package": {"ecosystem": "PyPI", "name": name}, "version": "1"} for name in ["one", "two"]
    ]
    results = batch_queries(queries, request)
    assert results[0]["vulnerability_ids"] == ["CVE-first", "CVE-last"]
    assert results[1]["vulnerability_ids"] == []
    assert {r["status"] for r in results} == {"queried"}


@pytest.mark.parametrize("mode", ["bad_length", "repeated_token", "invalid_result", "http_error"])
def test_incomplete_batch_is_unknown_even_when_no_matches_returned(mode) -> None:
    def request(url, payload):
        if mode == "bad_length":
            return {"results": []}
        if mode == "repeated_token":
            return {"results": [{"next_page_token": "repeat"}]}
        if mode == "invalid_result":
            return {"results": [{"error": "unsupported ecosystem"}]}
        raise OSError("HTTP 503")

    row = batch_queries([{"package": {"ecosystem": "PyPI", "name": "x"}, "version": "1"}], request)[
        0
    ]
    assert row["status"] == "unknown"
    assert row["error"]


def test_image_and_output_guards_do_not_accept_tags_or_replace_files(tmp_path: Path) -> None:
    (tmp_path / "protected").write_text("retained")
    with pytest.raises(ValueError, match="absent or empty"):
        Output(tmp_path)
    with pytest.raises(argparse.ArgumentTypeError, match="never a mutable tag"):
        validate_image("api=image:latest")
    output = Output(tmp_path / "new")
    output.write("result.json", b"original")
    with pytest.raises(FileExistsError):
        output.write("result.json", b"replacement")
    assert (output.path / "result.json").read_bytes() == b"original"
    with pytest.raises(ValueError, match="absent or empty"):
        Output(output.path)


def test_redhat_cpe_binding_excludes_other_minor_arch_and_missing_metadata() -> None:
    from scripts.scan_images_osv import redhat_ecosystems

    metadata = {
        "content_manifests": [
            {
                "path": "/root/buildinfo/content-sets.json",
                "content": {
                    "content_sets": [
                        "rhel-10-for-aarch64-baseos-rpms",
                        "rhel-10-for-x86_64-baseos-rpms",
                    ]
                },
            }
        ]
    }
    mapping = {
        "data": {
            "rhel-10-for-aarch64-baseos-rpms": {
                "cpes": [
                    "cpe:/o:redhat:enterprise_linux:10::baseos",
                    "cpe:/o:redhat:enterprise_linux:10.2",
                    "cpe:/o:redhat:enterprise_linux:10.1",
                    "cpe:/o:redhat:enterprise_linux:10.3",
                ]
            },
            "rhel-10-for-x86_64-baseos-rpms": {"cpes": ["cpe:/o:redhat:other:10.2"]},
        }
    }
    distro = {"ID": "rhel", "VERSION_ID": "10.2"}
    ecosystems, bindings = redhat_ecosystems(metadata, mapping, distro, "arm64")
    assert ecosystems == ["Red Hat:enterprise_linux:10.2", "Red Hat:enterprise_linux:10::baseos"]
    assert len(bindings) == 1
    with pytest.raises(ValueError, match="No official"):
        redhat_ecosystems({}, mapping, distro, "arm64")
    mapping["data"]["rhel-10-for-aarch64-baseos-rpms"]["cpes"] = ["https://untrusted.invalid/"]
    with pytest.raises(ValueError, match="Invalid Red Hat"):
        redhat_ecosystems(metadata, mapping, distro, "arm64")
