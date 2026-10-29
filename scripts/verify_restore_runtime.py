"""Bounded isolated restore startup/download proof; no seed, migration or worker.

Targets only an explicitly selected, manifest-bound arc_restore_<12hex> database.
Copies its registered source/ready-report keys into two new volumes, retaining
all targets. Database sessions and API storage/config mounts remain read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

if __package__:
    from .verify_restore import pg_fingerprint
else:
    from verify_restore import pg_fingerprint

ROOT = Path(__file__).resolve().parents[1]
NETWORK = "ai-review-console-upgrade_backend"
LIMIT_BYTES = 32 * 1024 * 1024
LIMIT_FILES = 500
COPY_CODE = r"""
import hashlib,json,os,stat,sys
from pathlib import Path,PurePosixPath
data=json.load(sys.stdin)
items=data["files"]
if len(items)>500 or sum(p["bytes"] for p in items)>32*1024*1024:
    raise RuntimeError("restore_file_capacity")
found=[]
for item in items:
    if item["kind"] not in {"source","report"}:
        raise RuntimeError("invalid_file_kind")
    key=PurePosixPath(item["key"])
    if key.is_absolute() or ".." in key.parts or not key.parts:
        raise RuntimeError("invalid_storage_key")
    root=Path("/source-documents" if item["kind"]=="source" else "/source-reports")
    path=root.joinpath(*key.parts)
    if not path.resolve().is_relative_to(root) or any(
        root.joinpath(*key.parts[:n]).is_symlink() for n in range(1,len(key.parts)+1)):
        raise RuntimeError("symlink_or_path_escape")
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size!=item["bytes"]:
        raise RuntimeError("selected_size_or_type_mismatch:"+item["key"])
    content=path.read_bytes()
    sha=hashlib.sha256(content).hexdigest()
    if sha!=item["sha256"]:
        raise RuntimeError("selected_hash_mismatch:"+item["key"])
    found.append(dict(item,source_uid=info.st_uid,source_gid=info.st_gid,
        source_mode=oct(stat.S_IMODE(info.st_mode)),source_sha256=sha))
if data["copy"]:
    if any(any(root.iterdir()) for root in (Path("/restore-documents"),Path("/restore-reports"))):
        raise RuntimeError("nonempty_restore_target")
    for root,uid in ((Path("/restore-documents"),10001),(Path("/restore-reports"),1000)):
        os.chown(root,uid,uid)
        os.chmod(root,0o755)
    for item in found:
        source_root=Path("/source-documents" if item["kind"]=="source" else "/source-reports")
        source=source_root/item["key"]
        root=Path("/restore-documents" if item["kind"]=="source" else "/restore-reports")
        uid=10001 if item["kind"]=="source" else 1000
        target=root/item["key"]
        target.parent.mkdir(parents=True,exist_ok=True)
        for parent in target.parents:
            if parent==root.parent: break
            os.chown(parent,uid,uid)
            os.chmod(parent,0o755)
        content=source.read_bytes()
        if len(content)!=item["bytes"] or hashlib.sha256(content).hexdigest()!=item["sha256"]:
            raise RuntimeError("source_changed_before_copy")
        with target.open("xb") as stream: stream.write(content)
        os.chown(target,uid,uid)
        os.chmod(target,0o644)
        copied=target.read_bytes()
        if hashlib.sha256(copied).hexdigest()!=item["sha256"]:
            raise RuntimeError("destination_hash_mismatch")
        info=target.stat()
        item.update(destination_uid=info.st_uid,destination_gid=info.st_gid,
            destination_mode=oct(stat.S_IMODE(info.st_mode)))
print(json.dumps({"files":found,"selected_count":len(found),
    "selected_bytes":sum(p["bytes"] for p in found),"copied":data["copy"]},sort_keys=True))
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def now() -> str:
    return datetime.now(UTC).isoformat()


class Commands:
    def __init__(self, output: Path):
        self.output = output
        self.records: list[dict] = []

    def run(
        self,
        label: str,
        command: list[str],
        *,
        data: bytes | None = None,
        environment: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        start = now()
        result = subprocess.run(
            command, input=data, capture_output=True, timeout=60, env=environment
        )
        for suffix, content in [("stdout", result.stdout), ("stderr", result.stderr)]:
            path = self.output / (label + "." + suffix)
            with path.open("xb") as target:
                target.write(content)
        self.records.append(
            {
                "label": label,
                "command": command,
                "started_at": start,
                "ended_at": now(),
                "exit_code": result.returncode,
                "stdin_sha256": digest(data) if data is not None else None,
                "stdout_sha256": digest(result.stdout),
                "stderr_sha256": digest(result.stderr),
                "environment_values_recorded": False,
            }
        )
        if check and result.returncode:
            raise RuntimeError(label + ": " + result.stderr.decode(errors="replace")[:2000])
        return result


def full_fingerprint(connection: psycopg.Connection) -> dict:
    names = [
        row["tablename"]
        for row in connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
    ]
    result = {}
    for name in names:
        if not re.fullmatch(r"[a-z_]+", name):
            raise ValueError("Unexpected public table identifier")
        rows = [
            row["row_to_json"]
            for row in connection.execute(
                sql.SQL("SELECT row_to_json(t) FROM {} t").format(sql.Identifier("public", name))
            )
        ]
        ordered = sorted(rows, key=canonical)
        result[name] = {"rows": len(rows), "content_sha256": digest(canonical(ordered))}
    return result


def read_database(database: str) -> tuple[dict, list[dict], list[dict], list[dict]]:
    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        user="review",
        password=os.getenv("POSTGRES_PASSWORD", "synthetic-demo-only"),
        dbname=database,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as connection:
        assert (
            connection.execute("SELECT current_database()").fetchone()["current_database"]
            == database
        )
        assert (
            connection.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"]
            == "on"
        )
        before = full_fingerprint(connection)
        sources = connection.execute(
            "SELECT id AS version_id,case_id,storage_key AS source_key,bytes,"
            "source_sha256 AS sha256 "
            "FROM document_versions WHERE storage_key IS NOT NULL ORDER BY id"
        ).fetchall()
        reports = connection.execute(
            "SELECT id AS report_id,case_id,document_version_id,format,"
            "storage_key AS artifact_key,bytes,sha256 "
            "FROM report_artifacts WHERE state=%s AND storage_key IS NOT NULL ORDER BY id",
            ("ready",),
        ).fetchall()
        cases = connection.execute(
            "SELECT id,status,current_document_version_id,decision FROM review_cases ORDER BY id"
        ).fetchall()
    return before, sources, reports, cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--restore-manifest",
        type=Path,
        required=True,
    )
    parser.add_argument("--restore-manifest-sha256", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--source-api", choices=["ai-review-console-upgrade-api-1"], required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume-empty-plan", type=Path)
    parser.add_argument("--resume-empty-plan-sha256")
    args = parser.parse_args()
    database, source_api, image = args.database, args.source_api, args.image
    if bool(args.resume_empty_plan) != bool(args.resume_empty_plan_sha256):
        raise ValueError("Resume requires the exact prior plan and its SHA-256")
    if not re.fullmatch(r"arc_restore_[a-f0-9]{12}", database):
        raise ValueError("Use an exact isolated arc_restore_<12hex> database")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("Use the exact current source container image SHA-256")
    if not re.fullmatch(r"[a-f0-9]{64}", args.restore_manifest_sha256):
        raise ValueError("Bind the selected restore manifest by SHA-256")
    selected_case_ids = set(args.case_id)
    if (
        len(args.case_id) > 3
        or len(selected_case_ids) != len(args.case_id)
        or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value)
               for value in args.case_id)
    ):
        raise ValueError("Select at most three distinct, exact case IDs")
    stem = database.replace("arc_restore_", "arc-restore-", 1)
    source_volume, report_volume, api_container = stem + "-source", stem + "-reports", stem + "-api"
    output = args.output.resolve()
    if (
        output.parent != Path("/private/tmp")
        or not re.fullmatch(r"arc-restore-runtime\.[A-Za-z0-9_-]+", output.name)
        or not output.is_dir()
    ):
        raise ValueError("Use a new mktemp -d /private/tmp/arc-restore-runtime.XXXXXX directory")
    if any(output.iterdir()):
        raise FileExistsError("Do not overwrite restore runtime evidence")
    if args.restore_manifest.is_symlink():
        raise ValueError("Select a regular restore manifest, not a symbolic link")
    manifest_path = args.restore_manifest.resolve(strict=True)
    if not manifest_path.is_file() or manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError("Restore manifest must be a regular file no larger than 1 MiB")
    manifest_bytes = manifest_path.read_bytes()
    if digest(manifest_bytes) != args.restore_manifest_sha256:
        raise ValueError("Restore manifest does not match its explicitly selected SHA-256")
    restore = json.loads(manifest_bytes)
    pg = restore["postgresql"]
    if (
        restore["contract"] != "ARC-UPGRADE@0.1.0"
        or "AC-17" not in restore["acceptance"]
        or pg["project"] != "ai-review-console-upgrade"
        or pg["container"] != "ai-review-console-upgrade-postgres-1"
        or pg["source_database"] != "review_console"
        or pg["schema_version"] != 2
        or pg["result"] != "passed"
        or pg["all_counts_and_content_hashes_equal"] is not True
        or pg["application_cutover"] is not False
    ):
        raise ValueError("Manifest is not a passed, isolated upgrade restore proof")
    if pg["restored_database"] != database:
        raise ValueError("Only the explicitly restored database is in scope")
    before, sources, reports, cases = read_database(database)
    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        user="review",
        password=os.getenv("POSTGRES_PASSWORD", "synthetic-demo-only"),
        dbname=database,
        options="-c default_transaction_read_only=on",
    ) as connection:
        assert pg_fingerprint(connection) == pg["source_and_restored_tables"]
    database_case_count = len(cases)
    database_case_ids = {case["id"] for case in cases}
    registered_file_count = len(sources) + len(reports)
    if selected_case_ids:
        if not selected_case_ids.issubset(database_case_ids):
            raise ValueError("Selected case is not present in the manifest-bound restored database")
        sources = [entry for entry in sources if entry["case_id"] in selected_case_ids]
        reports = [entry for entry in reports if entry["case_id"] in selected_case_ids]
        cases = [case for case in cases if case["id"] in selected_case_ids]
        if (
            {entry["case_id"] for entry in sources} != selected_case_ids
            or {entry["case_id"] for entry in reports} != selected_case_ids
        ):
            raise ValueError("Every selected case needs registered source and ready report files")
    if not sources or not reports:
        raise ValueError("Restore startup proof requires registered source and ready report files")
    items = [
        {"kind": "source", "key": p["source_key"], "bytes": p["bytes"], "sha256": p["sha256"],
         "case_id": p["case_id"], "document_version_id": p["version_id"], "report_id": None}
        for p in sources
    ] + [
        {"kind": "report", "key": p["artifact_key"], "bytes": p["bytes"], "sha256": p["sha256"],
         "case_id": p["case_id"], "document_version_id": p["document_version_id"],
         "report_id": p["report_id"]}
        for p in reports
    ]
    plan_fields = ("kind", "key", "bytes", "sha256", "case_id", "document_version_id", "report_id")
    for item in items:
        key = PurePosixPath(item["key"])
        if (
            key.is_absolute()
            or ".." in key.parts
            or not key.parts
            or str(key) != item["key"]
            or not re.fullmatch(r"[A-Za-z0-9._/-]{1,180}", item["key"])
        ):
            raise ValueError("Storage key is outside the bounded allowlist")
        if type(item["bytes"]) is not int or item["bytes"] <= 0:
            raise ValueError("Missing registered size")
        if not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise ValueError("Missing registered SHA-256")
    total = sum(p["bytes"] for p in items)
    if len(items) > LIMIT_FILES or total > LIMIT_BYTES:
        raise RuntimeError("Stop: restore file copy capacity exceeded")
    if len({(p["kind"], p["key"]) for p in items}) != len(items):
        raise ValueError("Duplicate selected storage keys")
    if args.resume_empty_plan:
        previous = args.resume_empty_plan
        if previous.is_symlink() or not previous.is_file() or previous.stat().st_size > 1024 * 1024:
            raise ValueError("Resume plan must be a bounded regular file")
        previous_bytes = previous.read_bytes()
        if digest(previous_bytes) != args.resume_empty_plan_sha256:
            raise ValueError("Prior selected-file plan hash mismatch")
        previous_plan = json.loads(previous_bytes)
        if (
            previous_plan["database"] != database
            or previous_plan["image"] != image
            or previous_plan["source_api"] != source_api
            or previous_plan["restore_manifest_sha256"] != args.restore_manifest_sha256
            or previous_plan["case_ids"] != sorted(selected_case_ids)
            or previous_plan["count"] != len(items)
            or previous_plan["bytes"] != total
            or previous_plan["files"] != items
        ):
            raise ValueError("Resume must use exactly the original selected-file plan")
    original_sqlite = ROOT / "review_console.sqlite3"
    sqlite_before = digest(original_sqlite.read_bytes())
    assert sqlite_before == restore["sqlite"]["source_sha256_before_and_after"]
    commands = Commands(output)
    inspect = json.loads(
        commands.run(
            "source-runtime",
            [
                "docker",
                "inspect",
                "--format",
                '{"image":{{json .Image}},"mounts":{{json .Mounts}},'
                '"networks":{{json .NetworkSettings.Networks}},'
                '"labels":{{json .Config.Labels}},"running":{{json .State.Running}}}',
                source_api,
            ],
        ).stdout
    )
    if (
        inspect["image"] != image
        or NETWORK not in inspect["networks"]
        or not inspect["running"]
        or inspect["labels"].get("com.docker.compose.project") != "ai-review-console-upgrade"
        or inspect["labels"].get("com.docker.compose.service") != "api"
    ):
        raise RuntimeError("Source runtime image/network differs from the fixed target")
    mounts = {p["Destination"]: p["Name"] for p in inspect["mounts"] if p["Type"] == "volume"}
    expected_mounts = {
        "/app/documents": "ai-review-console-upgrade_source-documents",
        "/app/artifacts": "ai-review-console-upgrade_report-artifacts",
        "/app/config": "ai-review-console-upgrade_flow-config",
    }
    if any(mounts.get(k) != v for k, v in expected_mounts.items()):
        raise RuntimeError("Source mount identity differs from the planned exact volumes")
    for volume in [source_volume, report_volume]:
        probe = commands.run(
            "preflight-" + volume, ["docker", "volume", "inspect", volume], check=False
        )
        if args.resume_empty_plan:
            if probe.returncode:
                raise RuntimeError("Resume requires both original exact target volumes")
            metadata = json.loads(probe.stdout)[0]
            labels = metadata.get("Labels") or {}
            if (
                metadata["Name"] != volume
                or labels.get("arc.restore.database") != database
                or labels.get("arc.restore.consumer") != "verify_restore_runtime.py"
            ):
                raise RuntimeError("Resume volume ownership does not match the prior plan")
        elif probe.returncode == 0 or b"no such volume" not in probe.stderr.lower():
            raise RuntimeError("Target already exists or cannot be resolved; preserve it")
    probe = commands.run("preflight-api", ["docker", "inspect", api_container], check=False)
    if probe.returncode == 0 or b"no such object" not in probe.stderr.lower():
        raise RuntimeError("Restore API target already exists or cannot be resolved; preserve it")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 8001))
    base = [
        "docker",
        "run",
        "--pull=never",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--user",
        "0:0",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--mount",
        "type=volume,source="
        + mounts["/app/documents"]
        + ",target=/source-documents,readonly,volume-nocopy",
        "--mount",
        "type=volume,source="
        + mounts["/app/artifacts"]
        + ",target=/source-reports,readonly,volume-nocopy",
    ]
    planned = {"files": items, "copy": False}
    if args.resume_empty_plan:
        commands.run(
            "empty-target-precheck",
            base + [
                "--mount", "type=volume,source=" + source_volume
                + ",target=/resume-source,readonly,volume-nocopy",
                "--mount", "type=volume,source=" + report_volume
                + ",target=/resume-reports,readonly,volume-nocopy",
                "--entrypoint", "python", image, "-c",
                "from pathlib import Path; "
                "assert all(not any(Path(p).iterdir()) "
                "for p in ['/resume-source','/resume-reports']), 'Nonempty resume target'; "
                "print('Both exact prior target volumes are empty')",
            ],
        )
    precheck = json.loads(
        commands.run(
            "selected-file-precheck",
            base + ["--entrypoint", "python", image, "-c", COPY_CODE],
            data=canonical(planned),
        ).stdout
    )
    assert precheck["selected_count"] == len(items) and precheck["selected_bytes"] == total
    assert [
        {key: entry[key] for key in plan_fields}
        for entry in precheck["files"]
    ] == items
    if digest(manifest_path.read_bytes()) != args.restore_manifest_sha256:
        raise RuntimeError("Selected restore manifest changed before copy")
    with (output / "selected-files.json").open("xb") as stream:
        stream.write(canonical({
            "restore_manifest_sha256": args.restore_manifest_sha256,
            "database": database,
            "image": image,
            "source_api": source_api,
            "count": len(items),
            "bytes": total,
            "case_ids": sorted(selected_case_ids),
            "scope": "selected cases" if selected_case_ids else "all registered files",
            "files": items,
        }))
    for volume in ([] if args.resume_empty_plan else [source_volume, report_volume]):
        commands.run(
            "create-" + volume,
            [
                "docker",
                "volume",
                "create",
                "--label",
                "arc.restore.database=" + database,
                "--label",
                "arc.restore.consumer=verify_restore_runtime.py",
                volume,
            ],
        )
    copied = json.loads(
        commands.run(
            "selected-file-copy",
            base
            + [
                "--cap-add=CHOWN",
                "--cap-add=FOWNER",
                # Only this bounded copy process can traverse the newly chowned
                # destination roots; all source mounts remain read-only.
                "--cap-add=DAC_OVERRIDE",
                "--mount",
                "type=volume,source=" + source_volume + ",target=/restore-documents,volume-nocopy",
                "--mount",
                "type=volume,source=" + report_volume + ",target=/restore-reports,volume-nocopy",
                "--entrypoint",
                "python",
                image,
                "-c",
                COPY_CODE,
            ],
            data=canonical({"files": items, "copy": True}),
        ).stdout
    )
    assert copied["selected_count"] == len(items)
    assert copied["selected_bytes"] == total
    assert [
        {key: entry[key] for key in plan_fields}
        for entry in copied["files"]
    ] == items
    for item in copied["files"]:
        owner = 10001 if item["kind"] == "source" else 1000
        assert item["destination_uid"] == item["destination_gid"] == owner
        assert item["destination_mode"] == "0o644"
    password = quote(os.getenv("POSTGRES_PASSWORD", "synthetic-demo-only"), safe="")
    environment = os.environ | {
        "DATABASE_URL": "postgresql+psycopg://review:"
        + password
        + "@postgres:5432/"
        + database
        + "?options="
        + quote("-c default_transaction_read_only=on", safe="")
    }
    start_command = [
        "docker",
        "run",
        "--pull=never",
        "-d",
        "--name",
        api_container,
        "--label",
        "arc.restore.database=" + database,
        "--label",
        "arc.restore.consumer=verify_restore_runtime.py",
        "--network",
        NETWORK,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--publish",
        "127.0.0.1:8001:8000",
        "--env",
        "DATABASE_URL",
        "--env",
        "DEMO_MODE=false",
        "--env",
        "DOCUMENTS_ROOT=/app/documents",
        "--env",
        "REPORTS_ROOT=/app/artifacts",
        "--env",
        "LANGFLOW_URL=http://langflow:7860",
        "--env",
        "LANGFLOW_FLOW_MANIFEST=/app/config/langflow-flows.json",
        "--mount",
        "type=volume,source=" + source_volume + ",target=/app/documents,readonly,volume-nocopy",
        "--mount",
        "type=volume,source=" + report_volume + ",target=/app/artifacts,readonly,volume-nocopy",
        "--mount",
        "type=volume,source="
        + mounts["/app/config"]
        + ",target=/app/config,readonly,volume-nocopy",
        image,
    ]
    container_id = (
        commands.run("start-isolated-api", start_command, environment=environment)
        .stdout.decode()
        .strip()
    )
    api_url = "http://127.0.0.1:8001"
    with httpx.Client(base_url=api_url, timeout=5) as client:
        deadline = time.monotonic() + 60
        while True:
            try:
                response = client.get("/api/health")
                response.raise_for_status()
                health = response.json()
                assert health["status"] == "ok"
                break
            except httpx.HTTPError:
                if time.monotonic() > deadline:
                    commands.run(
                        "api-failure-logs", ["docker", "logs", "--tail", "40", api_container]
                    )
                    raise RuntimeError(
                        "Restore API did not become healthy; retained for inspection"
                    ) from None
                time.sleep(1)
        listed = client.get("/api/cases")
        listed.raise_for_status()
        assert len(listed.json()) == database_case_count
        assert {p["id"] for p in listed.json()} == database_case_ids
        details = []
        for case in cases:
            response = client.get("/api/cases/" + case["id"])
            response.raise_for_status()
            payload = response.json()
            assert payload["status"] == case["status"]
            assert payload["decision"] == case["decision"]
            assert payload["current_document_version_id"] == case["current_document_version_id"]
            details.append(
                {
                    "case_id": case["id"],
                    "status": payload["status"],
                    "document_version_id": payload["current_document_version_id"],
                    "response_sha256": digest(response.content),
                    "http_status": response.status_code,
                }
            )
        downloads = []
        downloaded_total = 0
        for report in reports:
            path = "/api/cases/" + report["case_id"] + "/report/" + report["format"]
            data = bytearray()
            with client.stream("GET", path, params={"report_id": report["report_id"]}) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > report["bytes"] or downloaded_total + len(data) > LIMIT_BYTES:
                        raise RuntimeError(
                            "Stop: restored download exceeds registered/bounded size"
                        )
                sha = digest(data)
                assert len(data) == report["bytes"] and sha == report["sha256"]
                assert response.headers["x-content-sha256"] == sha
                downloaded_total += len(data)
                downloads.append(
                    {
                        "case_id": report["case_id"],
                        "report_id": report["report_id"],
                        "format": report["format"],
                        "bytes": len(data),
                        "sha256": sha,
                        "header_sha256": response.headers["x-content-sha256"],
                        "content_type": response.headers.get("content-type"),
                        "http_status": response.status_code,
                    }
                )
    after, _, _, _ = read_database(database)
    assert before == after and digest(original_sqlite.read_bytes()) == sqlite_before
    assert digest(manifest_path.read_bytes()) == args.restore_manifest_sha256
    target = json.loads(
        commands.run(
            "restored-runtime-inspect",
            [
                "docker",
                "inspect",
                "--format",
                '{"image":{{json .Image}},"mounts":{{json .Mounts}},'
                '"running":{{json .State.Running}}}',
                api_container,
            ],
        ).stdout
    )
    assert target["image"] == image and target["running"]
    assert len(target["mounts"]) == 3 and all(not p["RW"] for p in target["mounts"])
    logs = commands.run("restored-api-logs", ["docker", "logs", "--tail", "30", api_container])
    evidence = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["AC-17"],
        "producer": "scripts/verify_restore_runtime.py",
        "producer_sha256": digest(Path(__file__).read_bytes()),
        "checked_at": now(),
        "restore_manifest": str(manifest_path),
        "restore_manifest_sha256": args.restore_manifest_sha256,
        "resumed_empty_plan_sha256": args.resume_empty_plan_sha256,
        "database": database,
        "all_database_connections_read_only": True,
        "database_public_tables_before_and_after": before,
        "database_content_unchanged": before == after,
        "original_sqlite_sha256_before_and_after": sqlite_before,
        "selected_file_precheck": precheck,
        "selected_file_copy": copied,
        "selected_sources": sources,
        "selected_ready_reports": reports,
        "container_id": container_id,
        "container_name": api_container,
        "source_api": source_api,
        "image_id": image,
        "network": NETWORK,
        "api_url": api_url,
        "runtime_inspection": target,
        "health": health,
        "case_count": len(cases),
        "database_case_count": database_case_count,
        "case_readbacks": details,
        "file_scope": {
            "mode": "selected_cases" if selected_case_ids else "all_registered_files",
            "case_ids": sorted(selected_case_ids),
            "unselected_file_count": registered_file_count - len(items),
            "unselected_files_runtime_verified": False,
        },
        "downloads": downloads,
        "commands": commands.records,
        "retained": [database, source_volume, report_volume, api_container],
        "limits": {
            "files": len(items),
            "bytes": total,
            "max_files": LIMIT_FILES,
            "max_bytes": LIMIT_BYTES,
        },
        "mutations_not_performed": [
            "source database/old volumes/original SQLite change",
            "seed",
            "migration",
            "worker",
            "decision write",
            "application cutover",
            "delete/drop/cleanup",
        ],
        "limitations": (
            "Full database table fingerprints verified; file runtime proof covers only the "
            "explicit selected-files plan. Unselected database-associated files are not "
            "claimed restored or available. Not a complete file backup/production DR policy."
        ),
        "api_logs_sha256": digest(logs.stdout + logs.stderr),
        "result": "passed",
    }
    files = []
    for path in sorted(output.iterdir()):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": digest(data)})
    evidence["files"] = files
    (output / "manifest.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "manifest": str(output / "manifest.json"),
                "sha256": digest((output / "manifest.json").read_bytes()),
                "files_copied": len(items),
                "bytes_copied": total,
                "downloads_verified": len(downloads),
                "result": "passed",
            }
        )
    )


if __name__ == "__main__":
    main()
