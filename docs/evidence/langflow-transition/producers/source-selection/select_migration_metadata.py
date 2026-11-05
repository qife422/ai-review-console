"""Select exact immutable JSON members; derive capacity proof; never save ZIP/dumps."""
import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "ci/migration"
RUN = 41954322019
ARTIFACT = 13383340667
SOURCE = "480246c00a94ecee420f4d778ebf302acf3d4b79"
MEMBERS = (
    "manifest.json", "baseline-validation.json", "checkpoint-manifest.json",
    "checkpoint-summary.json", "upgrade-restore.json", "upgrade-summary.json",
    "rollback-restore.json", "rollback-summary.json",
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()

def inventory(root):
    paths = [path for path in root.rglob("*") if path.is_file()]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Unexpected symlink in bounded temporary inputs")
    return len(paths), sum(path.stat().st_size for path in paths)

raw = subprocess.check_output([
    "gh", "api", f"repos/qife422/ai-review-console/actions/artifacts/{ARTIFACT}/zip"
])
if len(raw) > 200 * 1024:
    raise ValueError("Unexpected metadata ZIP growth")
archive = zipfile.ZipFile(io.BytesIO(raw))
if set(archive.namelist()) != set(MEMBERS) | {"capacity.jsonl"}:
    raise ValueError("Unexpected artifact members")
if sum(item.file_size for item in archive.infolist()) > 256 * 1024:
    raise ValueError("Unexpected expanded metadata growth")
content = {name: archive.read(name) for name in archive.namelist()}
manifest = json.loads(content["manifest.json"])
if manifest["source_commit"] != SOURCE or str(manifest["run_id"]) != str(RUN):
    raise ValueError("Artifact source/run mismatch")
for item in manifest["files"]:
    data = content[item["path"]]
    if len(data) != item["bytes"] or digest(data) != item["sha256"]:
        raise ValueError("Producer manifest member integrity mismatch")
for name in ("checkpoint-summary.json", "upgrade-restore.json", "upgrade-summary.json",
             "rollback-restore.json", "rollback-summary.json"):
    if json.loads(content[name])["result"] != "passed":
        raise ValueError("Selected migration step did not pass")
checkpoint = json.loads(content["checkpoint-manifest.json"])
semantic = {db: {key: value for key, value in fields.items() if key != "physical_schema"}
            for db, fields in checkpoint["fingerprint"].items()}
semantic_sha = digest(canonical(semantic))
for name in ("upgrade-restore.json", "rollback-restore.json"):
    if json.loads(content[name])["details"]["semantic_fingerprint_sha256"] != semantic_sha:
        raise ValueError("Restored semantics do not match selected checkpoint")
capacity = [json.loads(line) for line in content["capacity.jsonl"].splitlines()]
if not capacity or any(item["available_bytes"] < item["floor_bytes"] for item in capacity):
    raise ValueError("Observed capacity floor was not maintained")
selection = {
    "producer": Path(__file__).name, "producer_sha256": digest(Path(__file__).read_bytes()),
    "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_id": RUN, "source_commit": SOURCE, "artifact_id": ARTIFACT,
    "archive_bytes": len(raw), "archive_sha256": digest(raw),
    "method": "ZIP received in memory; eight exact original JSON members selected unchanged; "
              "capacity JSONL reduced to sample count/minimum with original member size and SHA; "
              "producer member hashes and checkpoint/restored semantic hash independently checked",
    "members": [{"path": name, "bytes": len(data), "sha256": digest(data),
                 "selected_original": name in MEMBERS} for name, data in content.items()],
    "capacity_derived": {"sample_count": len(capacity),
                         "minimum_available_bytes": min(item["available_bytes"] for item in capacity),
                         "required_floor_bytes": 5368709120, "all_observed_samples_passed": True},
    "checkpoint_semantic_sha256": semantic_sha, "images": manifest["images"],
    "scope": "new GitHub runner synthetic baseline, separate upgrade and rollback namespaces",
    "not_selected": "ZIP, capacity JSONL, database dumps, storage payload files and container logs",
    "root_cause_limit": "New run observes compacted physical ordinals with logical schema and row "
                        "conservation; the first failed target's physical fields were not retained",
}
payloads = {name: content[name] for name in MEMBERS}
payloads["selection.json"] = json.dumps(selection, ensure_ascii=False, indent=2).encode()
new_bytes = sum(map(len, payloads.values()))
if new_bytes > 200 * 1024 or len(payloads) > 10:
    raise ValueError("Migration selection exceeds 200 KiB / 10 files")
ci_count, ci_bytes = inventory(ROOT / "ci")
_, temp_bytes = inventory(ROOT)
if ci_count + len(payloads) > 50 or ci_bytes + new_bytes > 1024 * 1024:
    raise ValueError("Combined selected CI evidence exceeds 1 MiB / 50 files")
if temp_bytes + new_bytes > 2 * 1024 * 1024:
    raise ValueError("Combined temporary inputs exceed 2 MiB")
if any((TARGET / name).exists() for name in payloads):
    raise ValueError("Selection would overwrite an existing input")
for name, data in payloads.items():
    with (TARGET / name).open("xb") as stream:
        stream.write(data)
print(json.dumps({"selected_files": len(payloads), "selected_bytes": new_bytes,
                  "combined_ci_files": ci_count + len(payloads),
                  "combined_ci_bytes": ci_bytes + new_bytes,
                  "combined_temp_bytes": temp_bytes + new_bytes,
                  "selection_sha256": digest(payloads["selection.json"]),
                  "selector_bytes": Path(__file__).stat().st_size,
                  "selector_sha256": digest(Path(__file__).read_bytes())}))
