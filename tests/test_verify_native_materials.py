"""Targeted collector safety boundaries; no Docker, network or native execution."""

import argparse
import json
import struct
from pathlib import Path

import pytest

from scripts import verify_native_materials as collector


@pytest.mark.parametrize("value", ["api=latest", "api=sha256:abc", "web=sha256:" + "a" * 64])
def test_rejects_mutable_or_out_of_scope_images(value):
    with pytest.raises(argparse.ArgumentTypeError):
        collector.image_argument(value)


def test_output_cannot_replace_prior_evidence(tmp_path):
    existing = tmp_path / "sealed"
    existing.mkdir()
    (existing / "manifest.json").write_text("fixed")
    with pytest.raises(ValueError, match="never overwrite"):
        collector.prepare_output(existing)
    assert (existing / "manifest.json").read_text() == "fixed"
    link = tmp_path / "link"
    link.symlink_to(existing)
    with pytest.raises(ValueError, match="symlink"):
        collector.prepare_output(link)


def test_shared_budget_counts_metadata_and_never_resets(tmp_path):
    first = tmp_path / "METADATA"
    first.write_bytes(b"abc")
    budget = collector.Budget(files=1, input_bytes=3, text_bytes=3)
    record, raw = collector.read_target(first, tmp_path, budget, retain_text=False)
    assert record["state"] == "recorded" and raw == b"abc" and "text" not in record
    next_image_budget = collector.Budget(**budget.remaining())
    skipped, raw = collector.read_target(first, tmp_path, next_image_budget)
    assert skipped["reason"] == "batch_file_limit" and raw is None
    assert next_image_budget.remaining() == dict(files=0, input_bytes=0, text_bytes=0)


def test_missing_escape_and_oversize_are_explicit_without_opening(tmp_path, monkeypatch):
    root = tmp_path / "driver"
    root.mkdir()
    outside = tmp_path / "secret.lic"
    outside.write_bytes(b"secret")
    link = root / "LICENSE"
    link.symlink_to(outside)
    budget = collector.Budget()
    record, _ = collector.read_target(link, root, budget)
    assert record["reason"] == "resolved_path_outside_approved_root"
    record, _ = collector.read_target(root / "redist.txt", root, budget)
    assert record["reason"] == "missing_file"
    monkeypatch.setattr(collector, "MAX_FILE_TEXT", 4)
    record, _ = collector.read_target(outside, tmp_path, budget)
    assert record["reason"] == "per_file_text_limit"
    assert budget.files == collector.MAX_FILES


def test_oversize_native_prefix_has_no_full_file_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, "MAX_FILE_TEXT", 4)
    library = tmp_path / "libdb2.so.1"
    library.write_bytes(b"abcdefgh")
    budget = collector.Budget(input_bytes=4)
    record, raw = collector.read_target(library, tmp_path, budget, text=False)
    assert record["state"] == "prefix_only" and record["sha256"] is None
    assert record["prefix_sha256"] == collector.digest(b"abcd") and raw == b"abcd"
    assert budget.input_bytes == 0 and budget.files == collector.MAX_FILES - 1
    assert "text" not in record


def test_elf_build_id_uses_note_structure_not_string_guessing():
    data = bytearray(160)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<I", data, 64, 4)
    struct.pack_into("<Q", data, 72, 128)
    struct.pack_into("<Q", data, 96, 20)
    struct.pack_into("<III", data, 128, 4, 4, 3)
    data[140:144], data[144:148] = b"GNU\0", b"\x01\x23\x45\x67"
    assert collector.elf_build_ids(bytes(data)) == dict(state="recorded", build_ids=["01234567"])
    assert collector.elf_build_ids(bytes(data[:120]))["state"] == "note_outside_prefix"


def test_followup_restores_exact_fixed_budget_and_rejects_tampering(tmp_path):
    source = Path(__file__).resolve().parents[1] / "compliance/native-baseline.json"
    baseline = collector.load_baseline(source)
    assert baseline["remaining_budget"] == collector.FOLLOWUP_REMAINING
    assert baseline["known_goal_input_bytes"] == 135700308
    altered = json.loads(source.read_text())
    altered["remaining_budget"]["files"] = 20
    destination = tmp_path / "altered-baseline.json"
    destination.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        collector.load_baseline(destination)


def test_followup_cannot_start_with_fresh_twenty_file_budget():
    with pytest.raises(ValueError, match="carried remaining quota"):
        collector.collect_followup("langflow", collector.Budget())


def test_followup_reads_only_missed_english_text_and_legacy_crypto(tmp_path, monkeypatch):
    root = tmp_path / "site-packages"
    license_dir = root / "clidriver/license"
    unix = license_dir / "UNIX"
    unix.mkdir(parents=True)
    (license_dir / "odbc_notices.txt").write_text("IBM notices")
    (license_dir / "odbc_REDIST.txt").write_text("prior fixed input; never reopen")
    (unix / "LI_en").write_text("English information")
    (unix / "LI_de").write_text("unselected translation")
    (unix / "entitlement.lic").write_text("secret license key")
    native = root / "psycopg2_binary.libs"
    native.mkdir()
    (native / "libcrypto-old.so.1.0.2k").write_bytes(b"\0OpenSSL 1.0.2k-fips\0")
    (native / "libcrypto-new.so.3").write_bytes(b"unselected modern crypto")
    (root / "unexpected.libs").mkdir()
    (root / "unexpected.libs/libcrypto.so.1.1").write_bytes(b"outside approved dirs")
    monkeypatch.setattr(collector.sysconfig, "get_path", lambda key: str(root))
    budget = collector.Budget(**collector.FOLLOWUP_REMAINING)
    result = collector.collect_followup("langflow", budget)
    recorded = [item for item in result["files"] if "bytes_read" in item]
    assert {Path(item["path"]).name for item in recorded} == {
        "odbc_notices.txt",
        "LI_en",
        "libcrypto-old.so.1.0.2k",
    }
    assert budget.files == 7
    crypto = next(item for item in recorded if item["purpose"] == "legacy_openssl_build_id")
    assert crypto["embedded_openssl_strings"] == ["OpenSSL 1.0.2k-fips"]
    assert not any("secret license key" in item.get("text", "") for item in result["files"])
    assert all(item.get("metadata_or_record_reread") is False for item in recorded)
    assert "unexpected.libs" not in str(result["directory_listing"])
