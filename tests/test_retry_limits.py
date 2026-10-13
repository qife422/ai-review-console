"""Isolated API retry tests; fixture failures do not represent Langflow execution."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from api.app import main
from api.app.database import get_session
from api.app.migrations import migrate
from api.app.models import AuditEvent, DocumentVersion, ReviewCase, WorkflowJob
from api.app.workflow import create_job


@pytest.fixture
def retry_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    target = create_engine(
        f"sqlite:///{tmp_path}/retry.sqlite3", connect_args={"check_same_thread": False}
    )
    migrate(target)
    factory = sessionmaker(target, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(main, "engine", target)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("DOCUMENTS_ROOT", str(tmp_path / "documents"))
    monkeypatch.setenv("REPORTS_ROOT", str(tmp_path / "reports"))

    def isolated_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    previous_override = main.app.dependency_overrides.get(get_session)
    main.app.dependency_overrides[get_session] = isolated_session
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            yield client, factory
    finally:
        if previous_override is None:
            main.app.dependency_overrides.pop(get_session, None)
        else:
            main.app.dependency_overrides[get_session] = previous_override
        target.dispose()


def _upload(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/cases",
        headers={"Idempotency-Key": "isolated-retry-upload"},
        data={"title": "虚构重试限制测试", "synthetic_confirmed": "true"},
        files={
            "file": (
                "synthetic.txt",
                b"SYNTHETIC DEMO DOCUMENT\nIsolated retry test only.",
                "text/plain",
            )
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def _fixture_failure(factory: sessionmaker[Session], case_id: str, job_id: str) -> None:
    """Set a deterministic unit fixture state without claiming an upstream failure."""
    with factory() as session:
        case = session.get(ReviewCase, case_id)
        job = session.get(WorkflowJob, job_id)
        case.status = "failed"
        job.state, job.phase, job.error_code = "failed", "failed", "synthetic_marker_missing"
        session.commit()


def _retry(
    client: TestClient, uploaded: dict[str, Any], prior_id: str, key: str
) -> Any:
    return client.post(
        f"/api/cases/{uploaded['case_id']}/retry",
        headers={"Idempotency-Key": key},
        json={"document_version_id": uploaded["document_version_id"], "job_id": prior_id},
    )


def test_latest_generation_and_cap_cannot_be_bypassed_with_old_job_or_new_key(
    retry_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = retry_client
    uploaded = _upload(client)
    original_id = uploaded["job_id"]
    _fixture_failure(factory, uploaded["case_id"], original_id)
    prior_id = original_id
    created: list[str] = []
    for generation in (1, 2, 3):
        response = _retry(client, uploaded, prior_id, f"isolated-retry-{generation}")
        assert response.status_code == 202, response.text
        job = response.json()
        assert job["retry_generation"] == generation
        assert job["job_id"] not in {original_id, *created}
        with factory() as session:
            assert (
                session.get(WorkflowJob, job["job_id"]).document_version_id
                == uploaded["document_version_id"]
            )
        created.append(job["job_id"])
        _fixture_failure(factory, uploaded["case_id"], job["job_id"])

        stale = _retry(client, uploaded, original_id, f"isolated-old-job-{generation}")
        assert stale.status_code == 409, stale.text
        assert stale.json()["code"] == "retry_not_allowed"
        prior_id = job["job_id"]

    fourth = _retry(client, uploaded, prior_id, "isolated-fourth-generation")
    assert fourth.status_code == 409, fourth.text
    assert fourth.json()["code"] == "retry_limit_reached"
    with factory() as session:
        jobs = session.scalars(
            select(WorkflowJob).where(WorkflowJob.case_id == uploaded["case_id"])
        ).all()
        assert sorted(job.retry_generation for job in jobs) == [0, 1, 2, 3]
        retries = session.scalars(
            select(AuditEvent).where(
                AuditEvent.case_id == uploaded["case_id"],
                AuditEvent.event_type == "intake_retry_requested",
            )
        ).all()
        assert len(retries) == 3
        assert session.get(ReviewCase, uploaded["case_id"]).risk_score is None


def test_retry_idempotency_reads_original_job_after_a_later_generation(
    retry_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = retry_client
    uploaded = _upload(client)
    _fixture_failure(factory, uploaded["case_id"], uploaded["job_id"])
    first = _retry(client, uploaded, uploaded["job_id"], "isolated-first-key")
    assert first.status_code == 202, first.text
    first_id = first.json()["job_id"]
    _fixture_failure(factory, uploaded["case_id"], first_id)
    second = _retry(client, uploaded, first_id, "isolated-second-key")
    assert second.status_code == 202, second.text
    repeated = _retry(client, uploaded, uploaded["job_id"], "isolated-first-key")
    assert repeated.status_code == 202, repeated.text
    assert repeated.json()["job_id"] == first_id
    assert repeated.json()["retry_generation"] == 1
    conflict = _retry(client, uploaded, first_id, "isolated-first-key")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    with factory() as session:
        jobs = session.scalars(
            select(WorkflowJob).where(WorkflowJob.case_id == uploaded["case_id"])
        ).all()
        assert sorted(job.retry_generation for job in jobs) == [0, 1, 2]
        retries = session.scalars(
            select(AuditEvent).where(
                AuditEvent.case_id == uploaded["case_id"],
                AuditEvent.event_type == "intake_retry_requested",
            )
        ).all()
        assert len(retries) == 2


def test_prior_job_from_older_document_version_cannot_retry_current_version(
    retry_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = retry_client
    uploaded = _upload(client)
    _fixture_failure(factory, uploaded["case_id"], uploaded["job_id"])
    with factory() as session:
        original = session.get(DocumentVersion, uploaded["document_version_id"])
        current = DocumentVersion(
            id="DV-isolated-current-version",
            case_id=uploaded["case_id"],
            version_number=2,
            source_sha256=original.source_sha256,
            hash_kind=original.hash_kind,
            storage_key=original.storage_key,
            mime_type=original.mime_type,
            bytes=original.bytes,
        )
        session.add(current)
        session.flush()
        current_job = create_job(
            session,
            kind="intake",
            case_id=uploaded["case_id"],
            version_id=current.id,
            payload={"unit": "current-version-fixture"},
            dedupe_key="isolated-current-version-job",
        )
        current_job.state = "failed"
        case = session.get(ReviewCase, uploaded["case_id"])
        case.current_document_version_id = current.id
        session.commit()
        current_id = current.id
    response = _retry(
        client,
        {**uploaded, "document_version_id": current_id},
        uploaded["job_id"],
        "isolated-old-version-retry",
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "retry_not_allowed"
    with factory() as session:
        assert len(
            session.scalars(
                select(WorkflowJob).where(WorkflowJob.case_id == uploaded["case_id"])
            ).all()
        ) == 2
        assert not session.scalars(
            select(AuditEvent).where(
                AuditEvent.case_id == uploaded["case_id"],
                AuditEvent.event_type == "intake_retry_requested",
            )
        ).all()
