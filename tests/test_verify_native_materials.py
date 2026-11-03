"""Targeted collector safety boundaries; no Docker, network or native execution."""

import argparse
import struct

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
