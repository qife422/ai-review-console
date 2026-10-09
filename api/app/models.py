from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(180), index=True)
    document_name: Mapped[str] = mapped_column(String(180))
    document_type: Mapped[str] = mapped_column(String(20))
    document_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    owner: Mapped[str] = mapped_column(String(80))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    original_text: Mapped[str] = mapped_column(Text)
    redacted_text: Mapped[str] = mapped_column(Text)
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    dimensions_json: Mapped[str] = mapped_column(Text, default="{}")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    pii_count: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    flow_run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="seed_demo")
    current_document_version_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    legacy_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    legacy_flow_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ruleset_version: Mapped[str] = mapped_column(String(40), default="2026.09-demo.1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text)
    document_version_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("case_id", "version_number"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    hash_kind: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_sections_json: Mapped[str] = mapped_column(Text, default="[]")
    redacted_sections_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    redaction_policy_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    redaction_policy_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("document_version_id", "revision"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    ruleset_version: Mapped[str] = mapped_column(String(40))
    ruleset_hash: Mapped[str] = mapped_column(String(64))
    rule_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))
    findings_json: Mapped[str] = mapped_column(Text)
    dimensions_json: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(
        ForeignKey("document_versions.id"), unique=True
    )
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(80))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True, default="")


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    decision_id: Mapped[str | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), unique=True)
    state: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    phase: Mapped[str] = mapped_column(String(40), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    retry_generation: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    lease_owner: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(80), nullable=True)
    execution_token: Mapped[str] = mapped_column(String(80))
    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload_json: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    langflow_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    flow_id: Mapped[str] = mapped_column(String(80))
    flow_hash: Mapped[str] = mapped_column(String(64))
    config_hash: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ReportArtifact(Base):
    __tablename__ = "report_artifacts"
    __table_args__ = (UniqueConstraint("snapshot_hash", "format"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"))
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"))
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True)
    format: Mapped[str] = mapped_column(String(10))
    storage_key: Mapped[str | None] = mapped_column(String(250), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_jobs.id"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(20), default="queued")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class UploadRequest(Base):
    __tablename__ = "upload_requests"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[str] = mapped_column(ForeignKey("review_cases.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("workflow_jobs.id"))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
