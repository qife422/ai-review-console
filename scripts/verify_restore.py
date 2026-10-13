"""Bounded restore acceptance for the isolated upgrade runtime only.

Reads the protected SQLite source and its previously migrated isolated copy.
Creates one explicitly named PostgreSQL restore database, retains it and the
small logical backup, and never drops a database, volume, table or evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "review_cases",
    "document_versions",
    "assessments",
    "decisions",
    "audit_events",
    "workflow_jobs",
    "report_artifacts",
)
MAX_DATABASE_BYTES = 128 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sqlite_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    # Identifiers are closed constants, never request input.
    if table not in {"review_cases", "audit_events", "legacy_review_cases", "legacy_audit_events"}:
        raise ValueError("Table is not allowlisted")
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY id")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor]


def sqlite_evidence(source: Path, migrated: Path) -> dict[str, Any]:
    if source != ROOT / "review_console.sqlite3" or source == migrated or not migrated.is_file():
        raise ValueError("Use the protected source and the existing isolated migrated copy")
    before_hash = digest(source.read_bytes())
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        original_cases, original_audits = (
            sqlite_rows(original, "review_cases"),
            sqlite_rows(original, "audit_events"),
        )
    with sqlite3.connect(migrated.as_uri() + "?mode=ro", uri=True) as target:
        legacy_cases = sqlite_rows(target, "legacy_review_cases")
        legacy_audits = sqlite_rows(target, "legacy_audit_events")
        current_cases = sqlite_rows(target, "review_cases")
        current_audits = sqlite_rows(target, "audit_events")
        assert original_cases == legacy_cases and original_audits == legacy_audits
        assert len(current_cases) == len(original_cases)
        assert not target.execute("PRAGMA foreign_key_check").fetchall()
        decided = sum(bool(row["decision"]) for row in original_cases)
        assert target.execute("SELECT count(*) FROM decisions").fetchone()[0] == decided
        by_id = {row["id"]: row for row in current_cases}
        for old in original_cases:
            new = by_id[old["id"]]
            for field in ("decision", "decision_reason", "decided_by", "decided_at"):
                assert new[field] == old[field]
            if old["status"] == "ready":
                assert new["status"] == "pending_approval" and new["legacy_status"] == "ready"
            assert new["flow_run_id"] is None and new["legacy_flow_label"] == old["flow_run_id"]
        for old in original_audits:
            assert next(row for row in current_audits if row["id"] == old["id"]) | {} == {
                **old,
                "document_version_id": None,
                "job_id": None,
                "decision_id": None,
                "request_id": None,
                "dedupe_key": None,
            }
    assert digest(source.read_bytes()) == before_hash
    return {
        "source": str(source),
        "source_bytes": source.stat().st_size,
        "source_sha256_before_and_after": before_hash,
        "isolated_migrated_copy": str(migrated),
        "copy_sha256": digest(migrated.read_bytes()),
        "original_case_count": len(original_cases),
        "original_audit_count": len(original_audits),
        "active_case_count": len(current_cases),
        "active_audit_count": len(current_audits),
        "preserved_decision_count": decided,
        "legacy_rows_exactly_match": True,
        "original_cases_content_hash": digest(canonical(original_cases)),
        "original_audits_content_hash": digest(canonical(original_audits)),
        "method": (
            "SQLite native .backup to isolated target; explicit v2 --allow-existing migration; "
            "readonly equality verification"
        ),
        "result": "passed; original source not changed",
    }


def pg_fingerprint(connection: psycopg.Connection) -> dict[str, Any]:
    result = {}
    for table in TABLES:
        rows = connection.execute(
            sql.SQL("SELECT row_to_json(t) FROM {} t ORDER BY id").format(
                sql.Identifier("public", table)
            )
        ).fetchall()
        result[table] = {
            "rows": len(rows),
            "content_sha256": digest(canonical([row[0] for row in rows])),
        }
    return result


def run(command: list[str]) -> None:
    result = subprocess.run(command, timeout=60, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[:2000])


def pg_restore_evidence(output: Path) -> dict[str, Any]:
    project = "ai-review-console-upgrade"
    container = f"{project}-postgres-1"
    password = os.getenv("POSTGRES_PASSWORD", "synthetic-demo-only")
    settings = {"host": "127.0.0.1", "port": 5433, "user": "review", "password": password}
    restore_name = f"arc_restore_{uuid.uuid4().hex[:12]}"
    dump_container = f"/tmp/{restore_name}.dump"
    backup = output / "review-console.dump"
    if backup.exists():
        raise FileExistsError("Never overwrite restore evidence")
    with psycopg.connect(**settings, dbname="review_console") as source:
        size = source.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        if size > MAX_DATABASE_BYTES:
            raise RuntimeError("Stop: bounded 128 MiB database estimate exceeded")
        before = pg_fingerprint(source)
    run(
        [
            "docker",
            "exec",
            container,
            "pg_dump",
            "-U",
            "review",
            "-d",
            "review_console",
            "--schema=public",
            "--no-owner",
            "--no-acl",
            "--format=custom",
            f"--file={dump_container}",
        ]
    )
    run(["docker", "cp", f"{container}:{dump_container}", str(backup)])
    if backup.stat().st_size > 32 * 1024 * 1024:
        raise RuntimeError("Stop: backup exceeds the bounded 32 MiB output estimate")
    with psycopg.connect(**settings, dbname="postgres", autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} OWNER review").format(sql.Identifier(restore_name))
        )
    # PostgreSQL's new database already owns a default public schema. Exclude
    # only that CREATE SCHEMA TOC item, retaining all tables/data/constraints.
    toc = subprocess.run(
        ["docker", "exec", container, "pg_restore", "--list", dump_container],
        check=True,
        timeout=60,
        capture_output=True,
        text=True,
    ).stdout
    selected = "\n".join(line for line in toc.splitlines() if " SCHEMA - public " not in line)
    toc_path = output / "restore-toc.list"
    toc_path.write_text(selected + "\n")
    toc_container = f"/tmp/{restore_name}.list"
    run(["docker", "cp", str(toc_path), f"{container}:{toc_container}"])
    run(
        [
            "docker",
            "exec",
            container,
            "pg_restore",
            "-U",
            "review",
            "-d",
            restore_name,
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            f"--use-list={toc_container}",
            dump_container,
        ]
    )
    with psycopg.connect(**settings, dbname=restore_name) as restored:
        after = pg_fingerprint(restored)
        version = restored.execute("SELECT max(version) FROM public.schema_migrations").fetchone()[
            0
        ]
    with psycopg.connect(**settings, dbname="review_console") as source:
        assert before == pg_fingerprint(source), (
            "Business data changed during snapshot; do not claim equality"
        )
    assert before == after and version == 2
    return {
        "project": project,
        "container": container,
        "source_database": "review_console",
        "source_database_bytes": size,
        "scope": "public schema business records only; excludes Langflow database and test schemas",
        "restored_database": restore_name,
        "application_cutover": False,
        "backup": str(backup),
        "backup_bytes": backup.stat().st_size,
        "backup_sha256": digest(backup.read_bytes()),
        "schema_version": version,
        "source_and_restored_tables": before,
        "all_counts_and_content_hashes_equal": True,
        "method": "native PostgreSQL logical dump/restore into a new isolated database",
        "toc_filter": (
            "skip only CREATE SCHEMA public, already present in empty target; "
            "no table/data filtered"
        ),
        "retention": "restore database and exact backup retained; no cleanup/drop authorization",
        "result": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-copy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (Path(tempfile.gettempdir()).resolve(), Path("/private/tmp"))
    if not output.is_dir() or not any(output.is_relative_to(root) for root in allowed):
        raise ValueError("Use an existing fresh system temporary directory")
    manifest = output / "restore.json"
    if manifest.exists():
        raise FileExistsError("Do not overwrite a restore manifest")
    evidence = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["AC-17"],
        "producer": "scripts/verify_restore.py",
        "producer_sha256": digest(Path(__file__).read_bytes()),
        "checked_at": datetime.now(UTC).isoformat(),
        "sqlite": sqlite_evidence(ROOT / "review_console.sqlite3", args.sqlite_copy.resolve()),
        "postgresql": pg_restore_evidence(output),
        "limitations": (
            "PostgreSQL legacy preservation is a separate fixture-based migration test; "
            "the original historical PostgreSQL volume was not started or changed."
        ),
    }
    manifest.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=2).encode())
    print(
        json.dumps(
            {"manifest": str(manifest), "sha256": digest(manifest.read_bytes()), "result": "passed"}
        )
    )


if __name__ == "__main__":
    main()
