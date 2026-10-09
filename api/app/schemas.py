from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Finding(BaseModel):
    rule_id: str
    category: str
    title: str
    severity: str
    points: int
    evidence: str
    recommendation: str
    section_id: str | None = None
    locator: str | None = None
    start: int | None = None
    end: int | None = None
    offset_basis: str | None = None


class AuditEventOut(BaseModel):
    id: int
    event_type: str
    actor: str
    detail: str
    occurred_at: datetime


class CaseSummary(BaseModel):
    id: str
    title: str
    document_name: str
    document_type: str
    status: str
    risk_score: int | None
    risk_level: str | None
    owner: str
    submitted_at: datetime
    due_at: datetime
    pii_count: int
    decision: str | None
    source_kind: str = "seed_demo"


class CaseDetail(CaseSummary):
    document_hash: str
    original_text: str
    redacted_text: str
    findings: list[Finding]
    dimensions: dict[str, int]
    warnings: list[str]
    decision_reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    flow_run_id: str | None
    ruleset_version: str
    audit_events: list[AuditEventOut]
    current_document_version_id: str | None = None
    assessment_id: str | None = None
    row_version: int = 1
    hash_kind: str = "synthetic_text"
    decision_id: str | None = None
    jobs: list[dict[str, object]] = Field(default_factory=list)
    reports: list[dict[str, object]] = Field(default_factory=list)
    parsed_sections: list[dict[str, object]] = Field(default_factory=list)
    redacted_sections: list[dict[str, object]] = Field(default_factory=list)
    source: dict[str, object] | None = None


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected", "changes_requested"]
    reason: str = Field(min_length=8, max_length=1000)
    document_version_id: str | None = None
    assessment_id: str | None = None
    expected_row_version: int | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class DashboardSummary(BaseModel):
    total_cases: int
    pending_approval: int
    high_risk: int
    completed: int
    average_score: float | None
    scored_cases: int = 0
    risk_distribution: dict[str, int]
    category_distribution: dict[str, int]
    system_status: dict[str, str]
    ruleset_version: str


class LangflowTaskRequest(BaseModel):
    case_id: str = Field(min_length=3, max_length=80)
    status: Literal["pending_approval"]
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high", "critical"]
    idempotency_key: str = Field(min_length=3, max_length=160)


class RetryRequest(BaseModel):
    document_version_id: str
    job_id: str


class ReportRetryRequest(BaseModel):
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    formats: list[Literal["json", "html", "pdf"]] = Field(min_length=1, max_length=3)


class Section(BaseModel):
    section_id: str = Field(min_length=1, max_length=100)
    locator: str = Field(min_length=1, max_length=180)
    text: str


class ParsedDocumentResult(BaseModel):
    filename: str
    mime_type: str
    sha256: str
    sections: list[Section] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class RedactedDocumentResult(BaseModel):
    sections: list[Section] = Field(min_length=1)
    count: int = Field(ge=0)
    policy_version: str


class AssessmentResult(BaseModel):
    score: int = Field(ge=0, le=100)
    level: Literal["low", "medium", "high", "critical"]
    dimensions: dict[str, int]
    findings: list[Finding]
    ruleset_version: str


class IntakeResult(BaseModel):
    schema_version: Literal["1.0"]
    case_id: str
    document_version_id: str
    job_id: str
    execution_token: str
    source_sha256: str
    payload_hash: str
    flow_id: str
    flow_hash: str
    config_hash: str
    ruleset_version: str
    ruleset_hash: str
    redaction_policy_version: str
    redaction_policy_hash: str
    parsed_document: ParsedDocumentResult
    redacted_document: RedactedDocumentResult
    assessment: AssessmentResult
    warnings: list[str] = Field(default_factory=list)


class ArtifactResult(BaseModel):
    format: Literal["json", "html", "pdf"]
    storage_key: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size: int = Field(gt=0, le=25 * 1024 * 1024)
    template_version: str


class ReportResult(BaseModel):
    job_id: str
    execution_token: str
    payload_hash: str
    case_id: str
    document_version_id: str
    decision_id: str
    snapshot_hash: str
    flow_id: str
    flow_hash: str
    artifacts: list[ArtifactResult]
    errors: list[dict[str, Any]] = Field(default_factory=list)
