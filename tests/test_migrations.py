from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import Column, ForeignKey, MetaData, Table, create_engine, inspect, select
from sqlalchemy.orm import Session

from api.app.migrations import AUDIT_ADDITIONS, CASE_ADDITIONS, migrate, require_schema
from api.app.models import AuditEvent, Decision, DocumentVersion, ReviewCase


def legacy_database(target: object, *, audit_fk: bool = False) -> None:
    metadata = MetaData()
    old_cases = Table(
        "review_cases",
        metadata,
        *[
            Column(
                column.name,
                column.type,
                primary_key=column.primary_key,
                nullable=False
                if column.name in {"risk_score", "risk_level", "flow_run_id"}
                else column.nullable,
            )
            for column in ReviewCase.__table__.columns
            if column.name not in CASE_ADDITIONS
        ],
    )
    old_audits = Table(
        "audit_events",
        metadata,
        *[
            Column(
                column.name,
                column.type,
                *([ForeignKey("review_cases.id")] if audit_fk and column.name == "case_id" else []),
                primary_key=column.primary_key,
                nullable=column.nullable,
            )
            for column in AuditEvent.__table__.columns
            if column.name not in AUDIT_ADDITIONS
        ],
    )
    metadata.create_all(target)
    at = datetime(2026, 9, 1, tzinfo=UTC)
    values = dict(
        title="虚构迁移样本",
        document_name="synthetic.txt",
        document_type="TXT",
        document_hash=hashlib.sha256(b"synthetic legacy source").hexdigest(),
        risk_score=28,
        risk_level="medium",
        owner="演示提交者",
        submitted_at=at,
        due_at=at,
        original_text="SYNTHETIC DEMO DOCUMENT\n不设责任上限",
        redacted_text="SYNTHETIC DEMO DOCUMENT\n不设责任上限",
        findings_json="[]",
        dimensions_json="{}",
        warnings_json="[]",
        pii_count=0,
        flow_run_id="lf-demo-migration",
        ruleset_version="2026.09-demo.1",
        created_at=at,
        updated_at=at,
        decision=None,
        decision_reason=None,
        decided_by=None,
        decided_at=None,
    )
    with target.begin() as connection:
        connection.execute(old_cases.insert(), {**values, "id": "legacy-ready", "status": "ready"})
        connection.execute(
            old_cases.insert(),
            {
                **values,
                "id": "legacy-approved",
                "status": "approved",
                "decision": "approved",
                "decision_reason": "保留这份历史虚构决定。",
                "decided_by": "演示审查员",
                "decided_at": at,
            },
        )
        connection.execute(
            old_audits.insert(),
            {
                "id": 1,
                "case_id": "legacy-approved",
                "event_type": "decision_recorded",
                "actor": "演示审查员",
                "detail": "历史审计原文不可覆盖",
                "occurred_at": at,
            },
        )


def test_fresh_schema_requires_explicit_migration(tmp_path: object) -> None:
    target = create_engine(f"sqlite:///{tmp_path}/fresh.sqlite3")
    with pytest.raises(RuntimeError, match="Run python"):
        require_schema(target)
    migrate(target)
    require_schema(target)
    migrate(target)
    assert "decisions" in inspect(target).get_table_names()


@pytest.mark.parametrize("audit_fk", [False, True])
def test_legacy_sqlite_is_protected_and_preserved(tmp_path: object, audit_fk: bool) -> None:
    target = create_engine(f"sqlite:///{tmp_path}/legacy.sqlite3")
    legacy_database(target, audit_fk=audit_fk)
    with pytest.raises(RuntimeError, match="existing_database_protected"):
        migrate(target)
    assert "legacy_review_cases" not in inspect(target).get_table_names()
    migrate(target, allow_existing=True)
    require_schema(target)
    assert "legacy_review_cases" in inspect(target).get_table_names()
    assert "legacy_audit_events" in inspect(target).get_table_names()
    assert inspect(target).get_foreign_keys("audit_events")[0]["referred_table"] == "review_cases"
    with Session(target) as session:
        ready = session.get(ReviewCase, "legacy-ready")
        approved = session.get(ReviewCase, "legacy-approved")
        assert ready.status == "pending_approval" and ready.legacy_status == "ready"
        assert ready.flow_run_id is None and ready.legacy_flow_label == "lf-demo-migration"
        assert approved.decision_reason == "保留这份历史虚构决定。"
        assert session.get(AuditEvent, 1).detail == "历史审计原文不可覆盖"
        assert len(session.scalars(select(Decision)).all()) == 1
        assert len(session.scalars(select(DocumentVersion)).all()) == 2
        assert all(
            item.hash_kind == "synthetic_text" and item.storage_key is None
            for item in session.scalars(select(DocumentVersion))
        )
    migrate(target, allow_existing=True)
    with Session(target) as session:
        assert len(session.scalars(select(AuditEvent)).all()) == 2
        assert len(session.scalars(select(Decision)).all()) == 1
