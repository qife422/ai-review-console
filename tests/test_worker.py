from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.app import worker
from api.app.langflow_client import LangflowError
from api.app.migrations import backfill_legacy, migrate
from api.app.models import WorkflowJob
from api.app.seed import seed_database
from api.app.workflow import create_job


@pytest.fixture
def jobs(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> tuple[worker.Worker, object, str]:
    target = create_engine(f"sqlite:///{tmp_path}/worker.sqlite3")
    migrate(target)
    factory = sessionmaker(target, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    with factory() as session:
        seed_database(session)
        backfill_legacy(session)
        session.flush()
        job = create_job(
            session,
            kind="intake",
            case_id="RC-260901-001",
            version_id="DV-RC-260901-001",
            payload={"unit": "lease-claim"},
            dedupe_key="worker-test-intake",
        )
        session.commit()
        job_id = job.id
    instance = worker.Worker("unit-worker")
    yield instance, target, job_id
    instance.langflow.close()
    instance.api.close()


def test_claim_and_recovery_keep_execution_identity(
    jobs: tuple[worker.Worker, object, str],
) -> None:
    instance, target, job_id = jobs
    claimed = instance.claim()
    assert claimed.id == job_id and claimed.attempt == 1
    assert instance.claim() is None
    token, lease = claimed.execution_token, claimed.lease_token
    with Session(target) as session:
        row = session.get(WorkflowJob, job_id)
        row.langflow_job_id = "unit-upstream-run"
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    recovered = instance.claim()
    assert recovered.execution_token == token
    assert recovered.langflow_job_id == "unit-upstream-run"
    assert recovered.lease_token != lease and recovered.attempt == 1
    assert instance.renew(recovered)


def test_retry_rotates_attempt_but_success_is_not_overwritten(
    jobs: tuple[worker.Worker, object, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, target, job_id = jobs
    claimed = instance.claim()
    monkeypatch.setattr(instance, "_post", lambda *_: {"accepted": True})
    instance.record_failure(
        claimed, LangflowError("langflow_unavailable", "unit network failure", True)
    )
    with Session(target) as session:
        row = session.get(WorkflowJob, job_id)
        assert row.state == "retry_wait"
        row.next_run_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    retry = instance.claim()
    assert retry.attempt == 2 and retry.execution_token != claimed.execution_token
    with Session(target) as session:
        row = session.get(WorkflowJob, job_id)
        row.state = "succeeded"
        row.result_hash = "a" * 64
        session.commit()
    instance.record_failure(retry, LangflowError("langflow_timeout", "late failure", True))
    with Session(target) as session:
        row = session.get(WorkflowJob, job_id)
        assert row.state == "succeeded" and row.result_hash == "a" * 64
        assert len(session.scalars(select(WorkflowJob)).all()) == 1
