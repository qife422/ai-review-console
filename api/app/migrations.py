"""Versioned additive demo migration. Run explicitly against an isolated target first.

SQLite retains the complete old review_cases table as legacy_review_cases because
SQLite cannot relax NOT NULL in place. No table, column, or old artifact is dropped.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from .database import engine
from .models import Assessment, AuditEvent, Base, Decision, DocumentVersion, ReviewCase
from .storage import content_hash

SCHEMA_VERSION = 2
CASE_ADDITIONS = {
    "source_kind": "VARCHAR(32) NOT NULL DEFAULT 'seed_demo'",
    "current_document_version_id": "VARCHAR(40)",
    "assessment_id": "VARCHAR(40)",
    "row_version": "INTEGER NOT NULL DEFAULT 1",
    "legacy_status": "VARCHAR(32)",
    "legacy_flow_label": "VARCHAR(80)",
}
AUDIT_ADDITIONS = {
    "document_version_id": "VARCHAR(40)",
    "job_id": "VARCHAR(40)",
    "decision_id": "VARCHAR(40)",
    "request_id": "VARCHAR(40)",
    "dedupe_key": "VARCHAR(180)",
}


def require_schema(target: Engine) -> None:
    with target.connect() as connection:
        try:
            version = connection.scalar(text("SELECT max(version) FROM schema_migrations"))
        except Exception as exc:
            raise RuntimeError(
                "Run python -m api.app.migrations before starting API/worker"
            ) from exc
    if version != SCHEMA_VERSION:
        raise RuntimeError(
            f"schema_version_mismatch: expected {SCHEMA_VERSION}, observed {version}"
        )


def migrate(target: Engine, *, allow_existing: bool = False) -> None:
    tables = set(inspect(target).get_table_names())
    if "schema_migrations" in tables:
        with target.connect() as connection:
            if (
                connection.scalar(text("SELECT max(version) FROM schema_migrations"))
                == SCHEMA_VERSION
            ):
                return
    if "review_cases" in tables and not allow_existing:
        raise RuntimeError(
            "existing_database_protected: restore to an isolated target and pass --allow-existing"
        )
    with target.begin() as connection:
        if "review_cases" in tables:
            if target.dialect.name == "sqlite":
                # Preserve legacy table and its indexes, then copy all original columns.
                old_columns = [
                    column["name"] for column in inspect(connection).get_columns("review_cases")
                ]
                ddl = str(CreateTable(ReviewCase.__table__).compile(connection))
                connection.execute(
                    text(
                        ddl.replace(
                            "CREATE TABLE review_cases", "CREATE TABLE review_cases_upgrade"
                        )
                    )
                )
                columns = ",".join(old_columns)
                additions = ",source_kind,row_version" if "source_kind" not in old_columns else ""
                values = ",'seed_demo',1" if additions else ""
                connection.execute(
                    text(
                        f"INSERT INTO review_cases_upgrade ({columns}{additions}) "
                        f"SELECT {columns}{values} FROM review_cases"
                    )
                )
                connection.execute(text("ALTER TABLE review_cases RENAME TO legacy_review_cases"))
                connection.execute(text("ALTER TABLE review_cases_upgrade RENAME TO review_cases"))
                # Renaming the parent rewrites SQLite child FKs to its legacy
                # name. Preserve and recreate the audit table against active
                # review_cases; retain every historical ID and original field.
                old_audit_columns = [
                    column["name"] for column in inspect(connection).get_columns("audit_events")
                ]
                connection.execute(text("ALTER TABLE audit_events RENAME TO legacy_audit_events"))
                connection.execute(CreateTable(AuditEvent.__table__))
                audit_columns_sql = ",".join(old_audit_columns)
                connection.execute(
                    text(
                        f"INSERT INTO audit_events ({audit_columns_sql}) "
                        f"SELECT {audit_columns_sql} FROM legacy_audit_events"
                    )
                )
            else:
                columns = {
                    column["name"] for column in inspect(connection).get_columns("review_cases")
                }
                for name, definition in CASE_ADDITIONS.items():
                    if name not in columns:
                        connection.execute(
                            text(f"ALTER TABLE review_cases ADD COLUMN {name} {definition}")
                        )
                for name in ("risk_score", "risk_level", "flow_run_id"):
                    connection.execute(
                        text(f"ALTER TABLE review_cases ALTER COLUMN {name} DROP NOT NULL")
                    )
            audit_columns = {
                column["name"] for column in inspect(connection).get_columns("audit_events")
            }
            for name, definition in AUDIT_ADDITIONS.items():
                if name not in audit_columns:
                    connection.execute(
                        text(f"ALTER TABLE audit_events ADD COLUMN {name} {definition}")
                    )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS arc_audit_dedupe ON audit_events(dedupe_key)"
                )
            )
            if target.dialect.name == "postgresql":
                connection.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence('audit_events','id'), "
                        "GREATEST(COALESCE((SELECT MAX(id) FROM audit_events),1),1), "
                        "EXISTS(SELECT 1 FROM audit_events))"
                    )
                )
        # Each table creation belongs to this explicit schema version, never API startup.
        for table in Base.metadata.sorted_tables:
            if table.name not in {"review_cases", "audit_events"} or "review_cases" not in tables:
                table.create(connection, checkfirst=True)
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"
            )
        )
        with Session(bind=connection) as session:
            backfill_legacy(session)
            session.flush()
        connection.execute(
            text("INSERT INTO schema_migrations (version,applied_at) VALUES (:version,:at)"),
            {"version": SCHEMA_VERSION, "at": datetime.now(UTC).isoformat()},
        )


def backfill_legacy(session: Session) -> None:
    for case in session.scalars(
        select(ReviewCase).where(ReviewCase.current_document_version_id.is_(None))
    ):
        case.source_kind = "seed_demo"
        case.legacy_status = case.status
        case.legacy_flow_label = case.flow_run_id
        case.flow_run_id = None
        case.row_version = 1
        if case.status == "ready":
            case.status = "pending_approval"
            session.add(
                AuditEvent(
                    case_id=case.id,
                    actor="schema-migration-v2",
                    event_type="legacy_ready_migrated",
                    detail="历史 ready 转为待人工审批；保留旧状态与虚构运行标签。",
                    dedupe_key=f"migration:v2:{case.id}",
                )
            )
        version_id, assessment_id = f"DV-{case.id}", f"AS-{case.id}"
        parsed = [
            {"section_id": "legacy-1", "locator": "synthetic-text:1", "text": case.original_text}
        ]
        redacted = [
            {"section_id": "legacy-1", "locator": "synthetic-text:1", "text": case.redacted_text}
        ]
        version = DocumentVersion(
            id=version_id,
            case_id=case.id,
            version_number=1,
            source_sha256=case.document_hash,
            hash_kind="synthetic_text",
            storage_key=None,
            mime_type="text/plain",
            bytes=None,
            parsed_sections_json=json.dumps(parsed, ensure_ascii=False),
            redacted_sections_json=json.dumps(redacted, ensure_ascii=False),
            warnings_json=case.warnings_json,
            redaction_policy_version="2026.09-demo.1",
            redaction_policy_hash=content_hash("legacy-demo-redaction"),
        )
        session.add(version)
        session.flush()
        assessment = Assessment(
            id=assessment_id,
            document_version_id=version_id,
            revision=1,
            ruleset_version=case.ruleset_version,
            ruleset_hash=content_hash("legacy-demo-rules"),
            rule_score=case.risk_score,
            risk_level=case.risk_level,
            findings_json=case.findings_json,
            dimensions_json=case.dimensions_json,
            source_kind="seed_demo",
        )
        session.add(assessment)
        session.flush()
        case.current_document_version_id, case.assessment_id = version_id, assessment_id
        if case.decision:
            session.add(
                Decision(
                    id=f"DC-{case.id}",
                    case_id=case.id,
                    document_version_id=version_id,
                    assessment_id=assessment_id,
                    decision=case.decision,
                    reason=case.decision_reason or "历史演示决定",
                    reviewer=case.decided_by or "历史演示审查员",
                    recorded_at=case.decided_at or case.submitted_at,
                    request_hash=content_hash({"legacy": case.id, "decision": case.decision}),
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    migrate(engine, allow_existing=args.allow_existing)
    print(f"schema_version={SCHEMA_VERSION}")


if __name__ == "__main__":
    main()
