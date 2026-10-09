"""PostgreSQL-only isolation, migration and concurrent transaction acceptance.

Set ARC_TEST_POSTGRES_URL to a disposable local database. Tests create named,
bounded schemas and retain them for inspection instead of dropping any database.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session
from test_migrations import legacy_database

from api.app.migrations import backfill_legacy, migrate
from api.app.models import AuditEvent, Decision, ReviewCase, WorkflowJob
from api.app.schemas import DecisionRequest
from api.app.seed import seed_database
from api.app.workflow import WorkflowError, record_decision

PG_URL = os.getenv("ARC_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="ARC_TEST_POSTGRES_URL not configured")


@pytest.fixture
def pg_engine() -> object:
    schema = f"arc_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(PG_URL)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    target = create_engine(PG_URL, connect_args={"options": f"-csearch_path={schema}"})
    yield target
    target.dispose()
    admin.dispose()


def test_postgres_legacy_migration_preserves_records(pg_engine: object) -> None:
    legacy_database(pg_engine)
    migrate(pg_engine, allow_existing=True)
    with Session(pg_engine) as session:
        assert session.get(ReviewCase, "legacy-ready").status == "pending_approval"
        assert session.get(ReviewCase, "legacy-approved").decided_by == "演示审查员"
        assert session.get(AuditEvent, 1).detail == "历史审计原文不可覆盖"
        assert session.scalar(select(func.count()).select_from(Decision)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2


def test_postgres_concurrent_decision_has_one_atomic_winner(pg_engine: object) -> None:
    migrate(pg_engine)
    with Session(pg_engine) as session:
        seed_database(session)
        backfill_legacy(session)
        session.commit()
        case = session.get(ReviewCase, "RC-260901-001")
        version_id, assessment_id, row_version = (
            case.current_document_version_id,
            case.assessment_id,
            case.row_version,
        )

    def submit(value: str) -> str:
        with Session(pg_engine, expire_on_commit=False) as session:
            try:
                record_decision(
                    session,
                    "RC-260901-001",
                    DecisionRequest(
                        decision=value,
                        reason=f"并发{value}的虚构审查意见。",
                        document_version_id=version_id,
                        assessment_id=assessment_id,
                        expected_row_version=row_version,
                    ),
                    f"reviewer-{value}",
                    f"concurrent-{value}",
                    f"request-{value}",
                )
                return "committed"
            except WorkflowError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(submit, ["approved", "rejected"]))
    assert sorted(outcomes) == ["committed", "decision_conflict"]
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Decision)
                .where(Decision.document_version_id == version_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.case_id == "RC-260901-001",
                    AuditEvent.event_type == "decision_recorded",
                )
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkflowJob)
                .where(WorkflowJob.case_id == "RC-260901-001", WorkflowJob.kind == "report")
            )
            == 1
        )
