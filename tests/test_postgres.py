"""PostgreSQL-only isolation, migration and concurrent transaction acceptance.

Set ARC_TEST_POSTGRES_URL to a disposable local database. Tests create named,
bounded schemas and retain them for inspection instead of dropping any database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import pytest
import test_workflow
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_migrations import legacy_database

from api.app import main, worker
from api.app.database import get_session
from api.app.langflow_client import LangflowError
from api.app.migrations import backfill_legacy, migrate
from api.app.models import Assessment, AuditEvent, Decision, ReviewCase, WorkflowJob
from api.app.schemas import DecisionRequest
from api.app.seed import seed_database
from api.app.workflow import WorkflowError, create_job, record_decision

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


def test_postgres_failure_waiting_on_callback_cannot_overwrite_success(
    pg_engine: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use a real PostgreSQL row-lock wait, not a sequential fake callback."""
    migrate(pg_engine)
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        backfill_legacy(session)
        session.flush()
        queued = create_job(
            session,
            kind="intake",
            case_id="RC-260901-001",
            version_id="DV-RC-260901-001",
            payload={"unit": "postgres-callback-failure-race"},
            dedupe_key="postgres-worker-race",
        )
        job_id = queued.id
        session.commit()
    instance = worker.Worker("postgres-race-validator")
    calls = []
    monkeypatch.setattr(instance, "_post", lambda *args: calls.append(args))
    claimed = instance.claim()
    reached_update = Event()

    @event.listens_for(pg_engine, "before_cursor_execute")
    def observe_update(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith("UPDATE workflow_jobs") and "execution_token" in statement:
            reached_update.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with factory.begin() as callback_session:
                row = callback_session.scalar(
                    select(WorkflowJob).where(WorkflowJob.id == job_id).with_for_update()
                )
                late_failure = executor.submit(
                    instance.record_failure,
                    claimed,
                    LangflowError("langflow_unavailable", "synthetic late failure", True),
                )
                assert reached_update.wait(5), "Failure did not reach its competing UPDATE"
                # This commit represents the result callback transaction winning.
                row.state, row.phase = "succeeded", "persisted"
                row.result_hash = "b" * 64
                row.completed_at = datetime.now(UTC)
            late_failure.result(timeout=5)
        with factory() as session:
            persisted = session.get(WorkflowJob, job_id)
            assert persisted.state == "succeeded" and persisted.phase == "persisted"
            assert persisted.result_hash == "b" * 64
            assert session.scalar(select(func.count()).select_from(WorkflowJob)) == 1
        assert calls == []
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe_update)
        instance.langflow.close()
        instance.api.close()


def test_postgres_duplicate_callback_commits_one_assessment_and_audit(
    pg_engine: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulated envelope, actual API and PostgreSQL concurrent transactions."""
    migrate(pg_engine)
    factory = sessionmaker(pg_engine, expire_on_commit=False)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "engine", pg_engine)
    monkeypatch.setattr(test_workflow, "SessionLocal", factory)

    def isolated_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    original_overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[get_session] = isolated_session
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            uploaded = test_workflow._upload(client)
            payload = test_workflow._intake_payload(uploaded)

            def submit(_: int) -> int:
                return client.post(
                    "/api/integrations/langflow/results",
                    headers=test_workflow.SERVICE_HEADERS,
                    json=payload,
                ).status_code

            with ThreadPoolExecutor(max_workers=2) as executor:
                assert list(executor.map(submit, [1, 2])) == [200, 200]
            changed = {**payload, "execution_token": "stale-postgres-test-token"}
            assert (
                client.post(
                    "/api/integrations/langflow/results",
                    headers=test_workflow.SERVICE_HEADERS,
                    json=changed,
                ).status_code
                == 409
            )
        with factory() as session:
            case = session.get(ReviewCase, uploaded["case_id"])
            assert case.status == "pending_approval" and case.assessment_id
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Assessment)
                    .where(Assessment.document_version_id == uploaded["document_version_id"])
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.case_id == uploaded["case_id"],
                        AuditEvent.event_type == "case_scored",
                    )
                )
                == 1
            )
            assert session.get(WorkflowJob, uploaded["job_id"]).state == "succeeded"
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(original_overrides)
