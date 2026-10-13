"""Business transactions owned by Review API, never by Langflow or the worker."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from .langflow_client import flow_configuration
from .models import (
    Assessment,
    AuditEvent,
    Decision,
    DocumentVersion,
    ReportArtifact,
    ReviewCase,
    WorkflowJob,
)
from .schemas import DecisionRequest, IntakeResult, ReportResult
from .storage import canonical_json, content_hash, documents_root, reports_root, resolve_storage

DECISIONS = {"approved", "rejected", "changes_requested"}
FORMATS = ("json", "html", "pdf")
RETRYABLE_ERRORS = {
    "langflow_timeout",
    "langflow_unavailable",
    "langflow_rate_limited",
    "langflow_http_error",
    "callback_unavailable",
    "callback_timeout",
    "worker_interrupted",
    "report_partial",
    "report_file_missing",
    "workflow_timeout",
    "langflow_run_lost",
    "result_not_persisted",
    "report_output_missing",
    "report_generation_failed",
}
INPUT_ERRORS = {
    "unsupported_type",
    "file_too_large",
    "empty_document",
    "encrypted_pdf",
    "synthetic_marker_missing",
    "invalid_encoding",
    "invalid_document",
    "unsupported_content",
    "requires_ocr",
    "text_too_large",
    "docx_limit_exceeded",
    "source_hash_mismatch",
    "policy_hash_mismatch",
    "ruleset_hash_mismatch",
    "redaction_result_invalid",
    "assessment_result_invalid",
}


class WorkflowError(ValueError):
    def __init__(self, code: str, detail: str, status: int = 409, retryable: bool = False):
        super().__init__(detail)
        self.code, self.detail, self.status, self.retryable = code, detail, status, retryable


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def audit(
    session: Session,
    case_id: str,
    event: str,
    detail: str,
    *,
    actor: str = "Review API",
    version_id: str | None = None,
    job_id: str | None = None,
    decision_id: str | None = None,
    request_id: str | None = None,
    dedupe_key: str | None = None,
) -> AuditEvent:
    record = AuditEvent(
        case_id=case_id,
        event_type=event,
        actor=actor,
        detail=detail,
        document_version_id=version_id,
        job_id=job_id,
        decision_id=decision_id,
        request_id=request_id,
        dedupe_key=dedupe_key,
    )
    session.add(record)
    return record


def ensure_queue_capacity(session: Session) -> None:
    """Reserve through one transaction lock for every business job producer."""
    if session.bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(268102026)"))
    states = {"queued", "retry_wait", "running"}
    persisted = (
        session.scalar(
            select(func.count()).select_from(WorkflowJob).where(WorkflowJob.state.in_(states))
        )
        or 0
    )
    pending = sum(isinstance(item, WorkflowJob) and item.state in states for item in session.new)
    if persisted + pending >= 50:
        raise WorkflowError("queue_capacity_exceeded", "The local queue is at capacity", 429, True)


def create_job(
    session: Session,
    *,
    kind: str,
    case_id: str,
    version_id: str,
    payload: dict[str, Any],
    dedupe_key: str,
    decision_id: str | None = None,
    retry_generation: int = 0,
) -> WorkflowJob:
    ensure_queue_capacity(session)
    config = flow_configuration(kind)
    fixed = {
        **payload,
        "case_id": case_id,
        "document_version_id": version_id,
        "flow_id": config["id"],
        "flow_hash": config["flow_hash"],
        "config_hash": config["config_hash"],
    }
    job = WorkflowJob(
        id=new_id("JB"),
        kind=kind,
        case_id=case_id,
        document_version_id=version_id,
        decision_id=decision_id,
        dedupe_key=dedupe_key,
        state="queued",
        phase="queued",
        attempt=0,
        retry_generation=retry_generation,
        execution_token=secrets.token_urlsafe(32),
        payload_json=canonical_json(fixed),
        payload_hash=content_hash(fixed),
        flow_id=config["id"],
        flow_hash=config["flow_hash"],
        config_hash=config["config_hash"],
        next_run_at=datetime.now(UTC),
    )
    session.add(job)
    return job


def intake_payload(version: DocumentVersion) -> dict[str, Any]:
    from review_core.redaction import REDACTION_POLICY_VERSION, policy_hash
    from review_core.risk import RULESET_VERSION, ruleset_hash

    return {
        "source_path": str(resolve_storage(documents_root(), version.storage_key or "")),
        "source_sha256": version.source_sha256,
        "ruleset_version": RULESET_VERSION,
        "ruleset_hash": ruleset_hash(),
        "redaction_policy_version": REDACTION_POLICY_VERSION,
        "redaction_policy_hash": policy_hash(),
    }


def job_out(job: WorkflowJob) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "kind": job.kind,
        "state": job.state,
        "phase": job.phase,
        "attempt": job.attempt,
        "retry_generation": job.retry_generation,
        "error_code": job.error_code,
        "error_detail": job.error_detail,
        "retryable": job.state == "failed"
        and job.error_code in RETRYABLE_ERRORS
        and job.retry_generation < 3,
        "langflow_job_id": job.langflow_job_id,
        "flow_id": job.flow_id,
        "flow_hash": job.flow_hash,
        "next_run_at": utc(job.next_run_at).isoformat(),
        "created_at": utc(job.created_at).isoformat(),
    }


def report_out(report: ReportArtifact) -> dict[str, Any]:
    return {
        "report_id": report.id,
        "format": report.format,
        "state": report.state,
        "snapshot_hash": report.snapshot_hash,
        "sha256": report.sha256,
        "bytes": report.bytes,
        "created_at": utc(report.created_at).isoformat(),
        "error_code": report.error_code,
        "download_url": f"/api/cases/{report.case_id}/report/{report.format}?report_id={report.id}"
        if report.state == "ready"
        else None,
    }


def build_snapshot(session: Session, case: ReviewCase, decision: Decision) -> dict[str, Any]:
    version = session.get(DocumentVersion, decision.document_version_id)
    assessment = session.get(Assessment, decision.assessment_id)
    if version is None or assessment is None or decision.decision not in DECISIONS:
        raise WorkflowError(
            "decision_snapshot_invalid", "Decision has no valid version and assessment"
        )
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id)
    ).all()
    snapshot = {
        "case_id": case.id,
        "title": case.title,
        "document_name": case.document_name,
        "document_version_id": version.id,
        "assessment_id": assessment.id,
        "decision_id": decision.id,
        "document_hash": version.source_sha256,
        "hash_kind": version.hash_kind,
        "source_kind": case.source_kind,
        "risk_score": assessment.rule_score,
        "risk_level": assessment.risk_level,
        "findings": json.loads(assessment.findings_json),
        "dimensions": json.loads(assessment.dimensions_json),
        "ruleset_version": assessment.ruleset_version,
        "ruleset_hash": assessment.ruleset_hash,
        "redaction_policy_version": version.redaction_policy_version,
        "redaction_policy_hash": version.redaction_policy_hash,
        "decision": decision.decision,
        "decision_reason": decision.reason,
        "decided_by": decision.reviewer,
        "decided_at": utc(decision.recorded_at).isoformat(),
        "generated_at": utc(decision.recorded_at).isoformat(),
        "data_classification": "SYNTHETIC_DEMO_ONLY",
        "workflow_engine": "Langflow",
        "audit_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "detail": event.detail,
                "occurred_at": utc(event.occurred_at).isoformat(),
            }
            for event in events
        ],
        "audit_through_id": max((event.id for event in events), default=0),
    }
    snapshot["snapshot_hash"] = content_hash(snapshot)
    return snapshot


def ensure_snapshot(session: Session, case: ReviewCase, decision: Decision) -> dict[str, Any]:
    if decision.snapshot_hash:
        return json.loads(decision.snapshot_json)
    snapshot = build_snapshot(session, case, decision)
    decision.snapshot_json, decision.snapshot_hash = (
        canonical_json(snapshot),
        snapshot["snapshot_hash"],
    )
    for format_name in FORMATS:
        session.add(
            ReportArtifact(
                id=new_id("RP"),
                case_id=case.id,
                document_version_id=decision.document_version_id,
                assessment_id=decision.assessment_id,
                decision_id=decision.id,
                snapshot_hash=decision.snapshot_hash,
                format=format_name,
                state="missing",
                generation_job_id=None,
            )
        )
    return snapshot


def record_decision(
    session: Session,
    case_id: str,
    payload: DecisionRequest,
    reviewer: str,
    key: str | None,
    request_id: str,
) -> ReviewCase:
    case = session.get(ReviewCase, case_id)
    if case is None:
        raise WorkflowError("case_not_found", "Review case not found", 404)
    request_hash = content_hash({**payload.model_dump(), "reviewer": reviewer})
    if key:
        existing = session.scalar(
            select(Decision).where(Decision.case_id == case_id, Decision.idempotency_key == key)
        )
        if existing:
            if existing.request_hash != request_hash:
                raise WorkflowError(
                    "idempotency_conflict", "This key was used for a different decision"
                )
            return case
    if case.source_kind == "uploaded_demo" and None in (
        payload.document_version_id,
        payload.assessment_id,
        payload.expected_row_version,
    ):
        raise WorkflowError(
            "version_required",
            "Uploaded documents require explicit version, assessment and row version",
            422,
        )
    version_id = payload.document_version_id or case.current_document_version_id
    assessment_id = payload.assessment_id or case.assessment_id
    expected = (
        payload.expected_row_version
        if payload.expected_row_version is not None
        else case.row_version
    )
    if (
        version_id != case.current_document_version_id
        or assessment_id != case.assessment_id
        or not assessment_id
    ):
        raise WorkflowError("stale_document_version", "Refresh the case before deciding")
    now = datetime.now(UTC)
    # Atomic compare-and-swap works for PostgreSQL and SQLite. Every side effect is
    # committed in the same transaction; a loser cannot add a decision or audit.
    result = session.execute(
        update(ReviewCase)
        .where(
            ReviewCase.id == case_id,
            ReviewCase.status == "pending_approval",
            ReviewCase.row_version == expected,
            ReviewCase.current_document_version_id == version_id,
            ReviewCase.assessment_id == assessment_id,
        )
        .values(
            status=payload.decision,
            decision=payload.decision,
            decision_reason=payload.reason,
            decided_by=reviewer,
            decided_at=now,
            row_version=expected + 1,
        )
    )
    if result.rowcount != 1:
        raise WorkflowError("decision_conflict", "A decision exists or the case has changed")
    decision = Decision(
        id=new_id("DC"),
        case_id=case.id,
        document_version_id=version_id,
        assessment_id=assessment_id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer=reviewer,
        recorded_at=now,
        idempotency_key=key,
        request_hash=request_hash,
    )
    session.add(decision)
    audit(
        session,
        case.id,
        "decision_recorded",
        f"决定：{payload.decision}。理由：{payload.reason}",
        actor=reviewer,
        version_id=version_id,
        decision_id=decision.id,
        request_id=request_id,
        dedupe_key=f"decision:{version_id}",
    )
    session.flush()
    session.refresh(case)
    snapshot = ensure_snapshot(session, case, decision)
    job = create_job(
        session,
        kind="report",
        case_id=case.id,
        version_id=version_id,
        decision_id=decision.id,
        payload={"snapshot": snapshot, "formats": list(FORMATS), "decision_id": decision.id},
        dedupe_key=f"report:{decision.snapshot_hash}:0",
    )
    session.flush()
    for artifact in session.scalars(
        select(ReportArtifact).where(ReportArtifact.snapshot_hash == decision.snapshot_hash)
    ):
        artifact.state, artifact.generation_job_id = "queued", job.id
    session.commit()
    session.refresh(case)
    return case


def validate_attempt(
    session: Session, payload: IntakeResult | ReportResult, kind: str
) -> WorkflowJob:
    job = session.scalar(
        select(WorkflowJob).where(WorkflowJob.id == payload.job_id).with_for_update()
    )
    if job is None:
        raise WorkflowError("job_not_found", "Workflow job not found", 404)
    if (
        job.kind != kind
        or job.case_id != payload.case_id
        or job.document_version_id != payload.document_version_id
        or job.execution_token != payload.execution_token
        or job.payload_hash != payload.payload_hash
        or job.flow_id != payload.flow_id
        or job.flow_hash != payload.flow_hash
    ):
        raise WorkflowError(
            "callback_binding_conflict", "Callback does not match the immutable job binding"
        )
    return job


def persist_intake(session: Session, payload: IntakeResult, request_id: str) -> dict[str, Any]:
    from review_core.redaction import redact_sections
    from review_core.risk import score_sections

    job = validate_attempt(session, payload, "intake")
    digest = content_hash(payload.model_dump())
    if job.result_hash:
        if job.result_hash != digest:
            raise WorkflowError(
                "callback_result_conflict", "A different result already exists for this job"
            )
        return {
            "accepted": True,
            "duplicate": True,
            "assessment_id": session.get(ReviewCase, job.case_id).assessment_id,
        }
    case = session.scalar(select(ReviewCase).where(ReviewCase.id == job.case_id).with_for_update())
    version = session.get(DocumentVersion, job.document_version_id)
    fixed = json.loads(job.payload_json)
    if (
        case is None
        or version is None
        or case.current_document_version_id != version.id
        or case.decision
        or job.state not in {"running", "retry_wait"}
        or version.source_sha256 != payload.source_sha256
        or payload.parsed_document.sha256 != version.source_sha256
        or payload.config_hash != job.config_hash
    ):
        raise WorkflowError(
            "callback_version_conflict", "Result is not valid for the active unapproved document"
        )
    for field in (
        "ruleset_version",
        "ruleset_hash",
        "redaction_policy_version",
        "redaction_policy_hash",
    ):
        if getattr(payload, field) != fixed[field]:
            raise WorkflowError(
                "callback_config_conflict", "Rules or redaction policy do not match this job"
            )
    original = [section.model_dump() for section in payload.parsed_document.sections]
    redacted = [section.model_dump() for section in payload.redacted_document.sections]
    if len({section["section_id"] for section in original}) != len(original):
        raise WorkflowError("sections_invalid", "Section IDs must be unique", 422)
    if sum(len(section["text"].encode()) for section in original) > 1024 * 1024:
        raise WorkflowError("text_too_large", "Callback text exceeds the 1 MiB limit", 422)
    if not any("SYNTHETIC DEMO DOCUMENT" in section["text"] for section in original):
        raise WorkflowError(
            "synthetic_marker_missing", "Parsed content lacks the required demo marker", 422
        )
    expected_redaction = redact_sections(original).to_dict()
    expected_assessment = score_sections(redacted).to_dict()
    expected_sections = [
        {"section_id": item["section_id"], "locator": item["locator"], "text": item["text"]}
        for item in expected_redaction["sections"]
    ]
    # Deterministic validation prevents forged scores/evidence or PII bypasses.
    if (
        redacted != expected_sections
        or payload.redacted_document.count != expected_redaction["count"]
    ):
        raise WorkflowError("redaction_result_invalid", "Redaction output is not reproducible", 422)
    if (
        payload.assessment.score != expected_assessment["score"]
        or payload.assessment.level != expected_assessment["level"]
        or payload.assessment.dimensions != expected_assessment["dimensions"]
        or [finding.model_dump() for finding in payload.assessment.findings]
        != [dict(item) for item in expected_assessment["findings"]]
    ):
        raise WorkflowError(
            "assessment_result_invalid", "Assessment or evidence is not reproducible", 422
        )
    version.parsed_sections_json, version.redacted_sections_json = (
        canonical_json(original),
        canonical_json(redacted),
    )
    version.warnings_json = canonical_json(payload.warnings)
    version.redaction_policy_version, version.redaction_policy_hash = (
        payload.redaction_policy_version,
        payload.redaction_policy_hash,
    )
    assessment = Assessment(
        id=new_id("AS"),
        document_version_id=version.id,
        revision=1,
        ruleset_version=payload.ruleset_version,
        ruleset_hash=payload.ruleset_hash,
        rule_score=payload.assessment.score,
        risk_level=payload.assessment.level,
        findings_json=canonical_json(expected_assessment["findings"]),
        dimensions_json=canonical_json(payload.assessment.dimensions),
        source_kind="uploaded_demo",
    )
    session.add(assessment)
    session.flush()
    case.status, case.assessment_id = "pending_approval", assessment.id
    case.risk_score, case.risk_level = assessment.rule_score, assessment.risk_level
    case.original_text, case.redacted_text = (
        "\n\n".join(item["text"] for item in original),
        "\n\n".join(item["text"] for item in redacted),
    )
    case.findings_json, case.dimensions_json, case.warnings_json = (
        assessment.findings_json,
        assessment.dimensions_json,
        version.warnings_json,
    )
    case.pii_count, case.flow_run_id, case.ruleset_version = (
        payload.redacted_document.count,
        job.langflow_job_id,
        payload.ruleset_version,
    )
    case.row_version += 1
    job.result_hash, job.state, job.phase, job.error_code, job.error_detail = (
        digest,
        "succeeded",
        "persisted",
        None,
        None,
    )
    audit(
        session,
        case.id,
        "case_scored",
        f"真实 Intake 结果已入库；规则分 {assessment.rule_score}，待人工决定。",
        actor="Langflow Intake Flow",
        version_id=version.id,
        job_id=job.id,
        request_id=request_id,
        dedupe_key=f"intake:{job.id}",
    )
    session.commit()
    return {"accepted": True, "duplicate": False, "assessment_id": assessment.id}


def persist_reports(session: Session, payload: ReportResult, request_id: str) -> dict[str, Any]:
    job = validate_attempt(session, payload, "report")
    decision = session.scalar(
        select(Decision).where(Decision.id == payload.decision_id).with_for_update()
    )
    if (
        decision is None
        or decision.id != job.decision_id
        or decision.snapshot_hash != payload.snapshot_hash
    ):
        raise WorkflowError("report_snapshot_conflict", "Report does not match the saved decision")
    fixed = json.loads(job.payload_json)
    expected_formats = set(fixed["formats"])
    artifacts = session.scalars(
        select(ReportArtifact)
        .where(ReportArtifact.snapshot_hash == decision.snapshot_hash)
        .with_for_update()
    ).all()
    if any(
        artifact.format in expected_formats
        and artifact.state != "ready"
        and artifact.generation_job_id != job.id
        for artifact in artifacts
    ):
        raise WorkflowError(
            "report_generation_conflict",
            "An older generation cannot change the active report job",
        )
    if job.state not in {"running", "retry_wait", "succeeded"}:
        raise WorkflowError("report_job_inactive", "A closed report job cannot publish results")
    if len({item.format for item in payload.artifacts}) != len(payload.artifacts):
        raise WorkflowError("report_formats_invalid", "Duplicate report formats", 422)
    for item in payload.artifacts:
        if item.format not in expected_formats or not item.storage_key.startswith(
            f"{decision.id}/{decision.snapshot_hash}/"
        ):
            raise WorkflowError(
                "report_path_invalid", "Report path is outside the immutable snapshot", 422
            )
        try:
            path = resolve_storage(reports_root(), item.storage_key)
            actual = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise WorkflowError(
                "report_file_missing", "Report bytes are unavailable", 409, True
            ) from exc
        if len(actual) != item.size or hashlib.sha256(actual).hexdigest() != item.sha256:
            raise WorkflowError(
                "report_integrity_invalid", "Report hash or size does not match", 422
            )
        artifact = session.scalar(
            select(ReportArtifact)
            .where(
                ReportArtifact.snapshot_hash == decision.snapshot_hash,
                ReportArtifact.format == item.format,
            )
            .with_for_update()
        )
        if artifact is None:
            raise WorkflowError("report_not_registered", "Report placeholder is missing")
        if artifact.state == "ready":
            if artifact.sha256 != item.sha256 or artifact.storage_key != item.storage_key:
                raise WorkflowError(
                    "report_immutable_conflict", "A ready report cannot be replaced"
                )
            continue
        if artifact.generation_job_id != job.id:
            raise WorkflowError(
                "report_generation_conflict",
                "An older generation cannot replace the active report job",
            )
        artifact.storage_key, artifact.sha256, artifact.bytes = (
            item.storage_key,
            item.sha256,
            item.size,
        )
        artifact.state, artifact.error_code, artifact.template_version = (
            "ready",
            None,
            item.template_version,
        )
        artifact.generation_job_id = job.id
        audit(
            session,
            job.case_id,
            "report_ready",
            f"{item.format.upper()} 报告已登记并校验字节哈希。",
            version_id=job.document_version_id,
            job_id=job.id,
            decision_id=decision.id,
            request_id=request_id,
            dedupe_key=f"report:{decision.snapshot_hash}:{item.format}",
        )
    ready = {item.format for item in artifacts if item.state == "ready"}
    missing = set(FORMATS) - ready
    errors = {
        item.get("format"): item.get("code", "report_generation_failed") for item in payload.errors
    }
    for artifact in artifacts:
        if artifact.format in missing and artifact.format in expected_formats:
            artifact.state, artifact.error_code = (
                "failed",
                errors.get(artifact.format, "report_format_missing"),
            )
    if not missing:
        job.state, job.phase, job.error_code = "succeeded", "registered", None
        job.result_hash = content_hash(
            {
                "snapshot": decision.snapshot_hash,
                "artifacts": sorted((item.format, item.sha256) for item in artifacts),
            }
        )
    else:
        job.state, job.phase, job.error_code = (
            ("retry_wait" if job.attempt < 3 else "failed"),
            "partial",
            "report_partial",
        )
        job.next_run_at = datetime.now(UTC) + timedelta(seconds=10 if job.attempt == 1 else 30)
        # A later attempt only regenerates formats that are still missing.
        fixed["formats"] = sorted(missing)
        # Keep immutable payload/hash unchanged. Worker selects missing formats from DB.
    session.commit()
    return {
        "accepted": True,
        "state": "partial" if missing else "ready",
        "missing_formats": sorted(missing),
    }
