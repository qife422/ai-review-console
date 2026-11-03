"""Collect targeted native redistribution materials from exact API/Langflow images.

Stdlib only. No image pull, mount, network, native-library execution or tree walk.
The whole batch shares 20 opened files, 64 MiB input and 4 MiB text. Metadata
files explicitly read below count too. Evidence is not distribution approval.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
import struct
import subprocess
import sys
import sysconfig
import threading
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path

MAX_FILES = 20
MAX_INPUT = 64 * 1024 * 1024
MAX_TEXT = 4 * 1024 * 1024
MAX_FILE_TEXT = 256 * 1024
MAX_JSON = 2 * 1024 * 1024
PRIOR_HASH_INPUT = 95_522_697
GOAL_HASH_LIMIT = 200 * 1024 * 1024
TARGETS = ("ibm_db", "psycopg_binary", "psycopg2_binary")
IMAGE_RE = re.compile(r"(api|langflow)=(sha256:[a-f0-9]{64})\Z")


def now():
    return datetime.now(UTC).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Budget:
    def __init__(self, files=MAX_FILES, input_bytes=MAX_INPUT, text_bytes=MAX_TEXT):
        if not (
            0 <= files <= MAX_FILES
            and 0 <= input_bytes <= MAX_INPUT
            and 0 <= text_bytes <= MAX_TEXT
        ):
            raise ValueError("Invalid remaining batch budget")
        self.files, self.input_bytes, self.text_bytes = files, input_bytes, text_bytes

    def remaining(self):
        return dict(files=self.files, input_bytes=self.input_bytes, text_bytes=self.text_bytes)


def elf_build_ids(data):
    """Parse GNU build-id PT_NOTE records present in the bounded ELF prefix."""
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] not in (1, 2) or data[5] not in (1, 2):
        return {"state": "not_supported_elf", "build_ids": []}
    endian = "<" if data[5] == 1 else ">"
    is64 = data[4] == 2
    try:
        phoff = struct.unpack_from(endian + ("Q" if is64 else "I"), data, 32 if is64 else 28)[0]
        entsize, count = struct.unpack_from(endian + "HH", data, 54 if is64 else 42)
        if count > 1024 or entsize < (56 if is64 else 32):
            return {"state": "unsupported_program_headers", "build_ids": []}
        ids, outside = [], False
        for i in range(count):
            start = phoff + i * entsize
            if start + entsize > len(data):
                outside = True
                continue
            if struct.unpack_from(endian + "I", data, start)[0] != 4:
                continue
            offset = struct.unpack_from(
                endian + ("Q" if is64 else "I"), data, start + (8 if is64 else 4)
            )[0]
            size = struct.unpack_from(
                endian + ("Q" if is64 else "I"), data, start + (32 if is64 else 16)
            )[0]
            end = offset + size
            if end > len(data):
                outside = True
                continue
            while offset + 12 <= end:
                namesz, descsz, kind = struct.unpack_from(endian + "III", data, offset)
                offset += 12
                desc = offset + ((namesz + 3) & ~3)
                next_note = desc + ((descsz + 3) & ~3)
                if next_note > end:
                    break
                if kind == 3 and data[offset : offset + namesz].rstrip(b"\0") == b"GNU":
                    ids.append(data[desc : desc + descsz].hex())
                offset = next_note
        return {
            "state": "recorded" if ids else "note_outside_prefix" if outside else "no_gnu_build_id",
            "build_ids": ids,
        }
    except (ValueError, struct.error):
        return {"state": "malformed_elf", "build_ids": []}


def read_target(path, root, budget, *, text=True, retain_text=True):
    result = dict(path=str(path), state="skipped", sha256=None)
    try:
        resolved, allowed = path.resolve(), root.resolve()
        result["resolved_path"] = str(resolved)
        if not resolved.is_relative_to(allowed):
            return result | {"reason": "resolved_path_outside_approved_root"}, None
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            return result | {"reason": "not_regular_file"}, None
        result["file_bytes"] = info.st_size
        if text and info.st_size > MAX_FILE_TEXT:
            return result | {"reason": "per_file_text_limit"}, None
        if budget.files == 0:
            return result | {"reason": "batch_file_limit"}, None
        # A very large driver is identified from its prefix, never called a full hash.
        amount = (
            info.st_size
            if text or info.st_size <= budget.input_bytes
            else min(MAX_FILE_TEXT, info.st_size)
        )
        if amount > budget.input_bytes:
            return result | {"reason": "batch_input_limit"}, None
        if text and amount > budget.text_bytes:
            return result | {"reason": "batch_text_limit"}, None
        with path.open("rb") as stream:
            budget.files -= 1
            data = stream.read(amount)
        budget.input_bytes -= len(data)
        if text:
            budget.text_bytes -= len(data)
        complete = len(data) == info.st_size
        result.update(
            state="recorded" if text else "hashed_only" if complete else "prefix_only",
            bytes_read=len(data),
            sha256=digest(data) if complete else None,
        )
        if not complete:
            result.update(
                prefix_sha256=digest(data),
                reason="full_file_exceeds_remaining_input; prefix_identification_only",
            )
        if text and retain_text:
            result["text"] = data.decode("utf-8", errors="replace")
        if not text:
            result["elf"] = elf_build_ids(data[:MAX_FILE_TEXT])
        return result, data
    except (OSError, RuntimeError) as error:
        return result | {
            "reason": "missing_file" if isinstance(error, FileNotFoundError) else "read_error",
            "error_type": type(error).__name__,
        }, None


def legal_candidate(path):
    name = path.name.lower()
    return (
        name == "odbc"
        or any(s in name for s in ("license", "licence", "redist", "copyright"))
        or name in ("version.txt", "db2level.txt", "li_en", "la_en", "notices")
        or name.endswith(".swidtag")
    )


def collect(name, budget):
    roots = sorted({Path(sysconfig.get_path(k)).resolve() for k in ("purelib", "platlib")})
    packages, records, candidates, listing = [], [], [], []
    for root in roots:
        # Only immediate site-packages entries, not arbitrary image contents.
        if not root.is_dir():
            continue
        dist_dirs = sorted(
            p
            for p in root.iterdir()
            if p.name.endswith(".dist-info") and any(p.name.startswith(n + "-") for n in TARGETS)
        )
        for dist in dist_dirs:
            meta_record, raw = read_target(dist / "METADATA", root, budget, retain_text=False)
            records.append(meta_record | {"purpose": "selected_distribution_metadata"})
            metadata = (
                Parser().parsestr(raw.decode("utf-8", errors="replace")) if raw is not None else {}
            )
            package = dict(
                name=metadata.get("Name", dist.name),
                version=metadata.get("Version"),
                license_expression=metadata.get("License-Expression"),
                root=str(root),
                dist_info=str(dist),
            )
            packages.append(package)
            record, raw = read_target(dist / "RECORD", root, budget, retain_text=False)
            records.append(record | {"purpose": "declared_file_list", "package": package["name"]})
            if raw is None:
                package["declared_file_state"] = "unavailable"
                continue
            declared = [
                row[0]
                for row in csv.reader(io.StringIO(raw.decode("utf-8", errors="replace")))
                if row
            ]
            # Bound metadata listing too; never silently discard an unbounded list.
            if len(declared) > 10000:
                package["declared_file_state"] = "over_10000_entries_not_processed"
                continue
            package["declared_file_state"] = "available"
            for rel in declared:
                p = Path(rel)
                if "clidriver" in p.parts and (legal_candidate(p) or p.suffix.lower() == ".lic"):
                    candidates.append((root / p, root, package["name"], "driver_legal_or_version"))
                if "libcrypto" in p.name and ".so.1.1" in p.name:
                    candidates.append(
                        (root / p, root, package["name"], "bundled_openssl_1_1_build_id")
                    )
                if "clidriver" in p.parts and p.name.startswith("libdb2.so"):
                    candidates.append((root / p, root, package["name"], "driver_elf_identity"))
            if package["name"].lower().replace("-", "_") == "ibm_db":
                driver = root / "clidriver"
                # Some installers omit driver files from RECORD. Explicit shallow
                # directories only; list names, no recursive traversal or content read.
                for directory in (
                    driver,
                    driver / "license",
                    driver / "license" / "odbc",
                    driver / "properties",
                    driver / "properties" / "version",
                ):
                    if not directory.is_dir() or not directory.resolve().is_relative_to(root):
                        listing.append(dict(path=str(directory), state="missing_or_outside_root"))
                        continue
                    entries = sorted(directory.iterdir())
                    if len(entries) > 256:
                        listing.append(
                            dict(
                                path=str(directory),
                                state="directory_listing_limit",
                                entry_count=len(entries),
                            )
                        )
                        continue
                    listing.append(dict(path=str(directory), entries=[p.name for p in entries]))
                    for p in entries:
                        if legal_candidate(p) or p.suffix.lower() == ".lic":
                            candidates.append((p, root, package["name"], "driver_legal_or_version"))
                for rel in ("redist.txt", "license/odbc", "version.txt", "lib/libdb2.so.1"):
                    p = driver / rel
                    candidates.append(
                        (
                            p,
                            root,
                            package["name"],
                            "driver_elf_identity"
                            if "/libdb2" in rel
                            else "driver_legal_or_version",
                        )
                    )
    seen = set()
    # Legal text before driver ELF and OpenSSL: metadata is already counted above.
    candidates.sort(
        key=lambda c: (
            0
            if c[3] == "driver_legal_or_version"
            else 1
            if c[3] == "bundled_openssl_1_1_build_id"
            else 2,
            str(c[0]),
        )
    )
    for p, root, owner, purpose in candidates:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        if p.suffix.lower() == ".lic":
            records.append(
                dict(
                    path=str(p),
                    purpose=purpose,
                    package=owner,
                    state="excluded",
                    reason="license_key_or_entitlement_file_not_collected",
                    sha256=None,
                )
            )
            continue
        record, _ = read_target(p, root, budget, text=purpose == "driver_legal_or_version")
        records.append(
            record
            | {
                "purpose": purpose,
                "declared_owner": owner,
                "owner_basis": (
                    "selected RECORD or explicit sibling clidriver directory; "
                    "not vendor-source proof"
                ),
            }
        )
    return dict(
        image_name=name,
        collected_at=now(),
        architecture=__import__("platform").machine(),
        packages=packages,
        files=records,
        driver_directory_listing=listing,
        remaining_budget=budget.remaining(),
        legal_approval=False,
        qualifications=[
            "ELF build-id and file hash do not prove corresponding vendor source or patches.",
            "Missing redist/agreement/version remains unresolved; no license-key bytes collected.",
            "This is a targeted follow-up, not a rerun of the prior 101-file inventory.",
        ],
    )


def image_argument(value):
    match = IMAGE_RE.fullmatch(value)
    if not match:
        raise argparse.ArgumentTypeError(
            "Use api|langflow=sha256:<64 lowercase hex>; tags rejected"
        )
    return match.group(1), match.group(2)


def prepare_output(path):
    if path.is_symlink():
        raise ValueError("Output symlink rejected")
    path = path.resolve()
    if path == Path(path.anchor) or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise ValueError("Output must be absent or empty; never overwrite")
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_bounded(command, payload):
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    exceeded = threading.Event()

    def consume(label, stream, limit):
        while chunk := stream.read(8192):
            if len(buffers[label]) + len(chunk) > limit:
                exceeded.set()
                proc.kill()
                break
            buffers[label].extend(chunk)
        stream.close()

    readers = [
        threading.Thread(target=consume, args=(label, getattr(proc, label), limit))
        for label, limit in (("stdout", MAX_JSON), ("stderr", 16384))
    ]
    for reader in readers:
        reader.start()
    reason = None
    try:
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        reason = "command_timeout"
        proc.kill()
        proc.wait()
    for reader in readers:
        reader.join(timeout=5)
    if exceeded.is_set():
        reason = "command_output_limit"
    return proc.returncode, reason, bytes(buffers["stdout"]), bytes(buffers["stderr"])


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", type=image_argument, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if len(args.image) > 2 or len({n for n, _ in args.image}) != len(args.image):
        parser.error("At most two distinct API/Langflow images")
    output = prepare_output(args.output_dir)
    producer = Path(__file__).read_bytes()
    budget, results, failed = Budget(), [], False
    # Driver-bearing image first; one remaining budget is passed into the next.
    for name, image_id in sorted(args.image, key=lambda pair: pair[0] != "langflow"):
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--pull",
            "never",
            "--read-only",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "512m",
            "--pids-limit",
            "64",
            "--log-driver",
            "none",
            "--entrypoint",
            "python",
            image_id,
            "-",
            "--_collect",
            name,
            json.dumps(budget.remaining()),
        ]
        started = now()
        code, reason, stdout, stderr = run_bounded(command, producer)
        record = dict(
            image_name=name,
            image_id=image_id,
            command=command,
            started_at=started,
            ended_at=now(),
            producer_sha256=digest(producer),
            stdin_sha256=digest(producer),
            stdout_sha256=digest(stdout),
            exit_code=code,
            stop_reason=reason,
            stderr=stderr.decode("utf-8", errors="replace"),
            collection_state="failed",
        )
        if code == 0 and reason is None:
            try:
                result = json.loads(stdout)
                remaining = result["remaining_budget"]
                if any(remaining[k] > v for k, v in budget.remaining().items()):
                    raise ValueError("Invalid returned shared budget")
                budget = Budget(**remaining)
                record.update(result=result, collection_state="collected_with_explicit_scope")
            except (ValueError, KeyError, TypeError) as error:
                record["error"] = str(error)
        if record["collection_state"] == "failed":
            failed = True
        results.append(record)
        # Failed child budget is unknown: do not run another image with a reset.
        if failed:
            break
    report = dict(
        created_at=now(),
        producer="scripts/verify_native_materials.py",
        producer_sha256=digest(producer),
        images=results,
        remaining_budget=budget.remaining(),
        legal_approval=False,
        limits=dict(
            files=MAX_FILES,
            input_bytes=MAX_INPUT,
            text_bytes=MAX_TEXT,
            per_text_file_bytes=MAX_FILE_TEXT,
            json_bytes=MAX_JSON,
        ),
        prior_inventory=dict(
            paths=101, planned_paths=100, deviation_retained=True, input_bytes=PRIOR_HASH_INPUT
        ),
        goal_hash_input_limit_bytes=GOAL_HASH_LIMIT,
        goal_known_input_bytes=PRIOR_HASH_INPUT + MAX_INPUT - budget.input_bytes,
    )
    raw = encode(report)
    if len(raw) >= MAX_JSON:
        # Do not serialize oversized contents. Preserve hashes/reasons, never call
        # dropped text delivered. Input/file budgets remain exactly as collected.
        for image in results:
            for item in image.get("result", {}).get("files", []):
                if "text" in item:
                    item.pop("text")
                    item["text_output_state"] = "omitted_due_to_batch_json_limit"
        raw = encode(report)
    if len(raw) >= MAX_JSON:
        raise ValueError("JSON limit exceeded; no evidence written")
    with (output / "materials.json").open("xb") as stream:
        stream.write(raw)
    manifest = encode(
        dict(
            created_at=now(),
            producer_sha256=digest(producer),
            legal_approval=False,
            files=[dict(path="materials.json", bytes=len(raw), sha256=digest(raw))],
            qualification=(
                "Collection success is not source correspondence or distribution approval."
            ),
        )
    )
    if len(raw) + len(manifest) >= MAX_JSON:
        raise ValueError("Aggregate JSON limit exceeded")
    with (output / "manifest.json").open("xb") as stream:
        stream.write(manifest)
    print(json.dumps(dict(output_dir=str(output), legal_approval=False, failed=failed)))
    return int(failed)


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--_collect":
        # stdin invocation: '-' is argv[0], then exactly three private arguments.
        raise SystemExit("Invalid helper argument count")
    if len(sys.argv) == 4 and sys.argv[1] == "--_collect":
        if sys.argv[2] not in ("api", "langflow"):
            raise SystemExit("Invalid private helper image alias")
        result = collect(sys.argv[2], Budget(**json.loads(sys.argv[3])))
        # Reserve room for the second image and host manifest before emitting.
        if len(encode(result)) > MAX_JSON // 3:
            for item in result["files"]:
                if "text" in item:
                    item.pop("text")
                    item["text_output_state"] = "omitted_due_to_helper_json_limit"
        print(json.dumps(result))
    else:
        raise SystemExit(main())
