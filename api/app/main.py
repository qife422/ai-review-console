from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from review_core.parsing import DocumentParseError, validate_document_bytes

from .database import SessionLocal, engine, get_session
from .langflow_client import LangflowError, flow_configuration
from .migrations import backfill_legacy, require_schema
from .models import (
    AuditEvent,
    Decision,
    DocumentVersion,
    ReportArtifact,
    ReviewCase,
    UploadRequest,
    WorkerHeartbeat,
    WorkflowJob,
)
from .schemas import (
    CaseDetail,
    CaseSummary,
    DashboardSummary,
    DecisionRequest,
    IntakeResult,
    LangflowTaskRequest,
    ReportResult,
    ReportRetryRequest,
    RetryRequest,
)
from .seed import seed_database
from .storage import (
    MAX_FILE_BYTES,
    MIME_TYPES,
    content_hash,
    reports_root,
    resolve_storage,
    save_document,
)
from .workflow import (
    DECISIONS,
    FORMATS,
    WorkflowError,
    audit,
    create_job,
    ensure_queue_capacity,
    ensure_snapshot,
    intake_payload,
    job_out,
    new_id,
    persist_intake,
    persist_reports,
    record_decision,
    report_out,
    utc,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    require_schema(engine)
    with SessionLocal() as session:
        if os.getenv("DEMO_MODE", "true").lower() == "true":
            seed_database(session)
            backfill_legacy(session)
            session.flush()
            for case in session.scalars(select(ReviewCase).where(ReviewCase.decision.is_not(None))):
                decision = session.scalar(
                    select(Decision).where(
                        Decision.document_version_id == case.current_document_version_id
                    )
                )
                if decision:
                    ensure_snapshot(session, case, decision)
            session.commit()
    yield


app = FastAPI(
    title="AI Review Console API",
    version="0.2.0",
    lifespan=lifespan,
    description="Synthetic document review built on Langflow. Human decisions are required.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(
        ","
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Reviewer", "Idempotency-Key"],
)
SessionDep = Annotated[Session, Depends(get_session)]
_probe_cache: dict[str, Any] = {}


@app.middleware("http")
async def request_context(request: Request, call_next: Any) -> Response:
    request.state.request_id = str(uuid.uuid4())
    limit = (
        4 * 1024 * 1024 if request.url.path.startswith("/api/integrations/") else 11 * 1024 * 1024
    )
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        return error_response(request, "content_length_invalid", "Invalid content length", 400)
    if length > limit:
        return error_response(
            request, "request_too_large", "Request exceeds the permitted size", 413
        )
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
                return error_response(
                    request, "request_too_large", "Request exceeds the permitted size", 413
                )
            body.extend(chunk)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error_response(
    request: Request, code: str, detail: str, status: int, retryable: bool = False
) -> JSONResponse:
    return JSONResponse(
        {
            "code": code,
            "detail": detail,
            "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            "retryable": retryable,
        },
        status_code=status,
    )


@app.exception_handler(WorkflowError)
async def workflow_error(request: Request, exc: WorkflowError) -> JSONResponse:
    return error_response(request, exc.code, exc.detail, exc.status, exc.retryable)


@app.exception_handler(LangflowError)
async def langflow_error(request: Request, exc: LangflowError) -> JSONResponse:
    return error_response(request, exc.code, exc.detail, 503, exc.retryable)


@app.exception_handler(DocumentParseError)
async def parser_error(request: Request, exc: DocumentParseError) -> JSONResponse:
    status = (
        413
        if exc.code in {"file_too_large", "text_too_large"}
        else 415
        if exc.code == "unsupported_type"
        else 422
    )
    return error_response(request, exc.code, exc.detail, status)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
    return error_response(request, "validation_error", "Request fields or content are invalid", 422)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return error_response(request, "http_error", str(exc.detail), exc.status_code)


def _loads(value: str) -> Any:
    return json.loads(value)


def _case_summary(case: ReviewCase) -> CaseSummary:
    return CaseSummary(
        id=case.id,
        title=case.title,
        document_name=case.document_name,
        document_type=case.document_type,
        status=case.status,
        risk_score=case.risk_score,
        risk_level=case.risk_level,
        owner=case.owner,
        submitted_at=utc(case.submitted_at),
        due_at=utc(case.due_at),
        pii_count=case.pii_count,
        decision=case.decision,
        source_kind=case.source_kind,
    )


def _case_detail(session: Session, case: ReviewCase) -> CaseDetail:
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.case_id == case.id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    ).all()
    version = (
        session.get(DocumentVersion, case.current_document_version_id)
        if case.current_document_version_id
        else None
    )
    jobs = session.scalars(
        select(WorkflowJob)
        .where(WorkflowJob.case_id == case.id)
        .order_by(WorkflowJob.created_at.desc())
    ).all()
    reports = session.scalars(
        select(ReportArtifact)
        .where(ReportArtifact.case_id == case.id)
        .order_by(ReportArtifact.created_at)
    ).all()
    decision = session.scalar(
        select(Decision).where(Decision.document_version_id == case.current_document_version_id)
    )
    intake = next(
        (
            job
            for job in jobs
            if job.kind == "intake" and job.document_version_id == case.current_document_version_id
        ),
        None,
    )
    return CaseDetail(
        **_case_summary(case).model_dump(),
        document_hash=case.document_hash,
        original_text=case.original_text,
        redacted_text=case.redacted_text,
        findings=_loads(case.findings_json),
        dimensions=_loads(case.dimensions_json),
        warnings=_loads(case.warnings_json),
        decision_reason=case.decision_reason,
        decided_by=case.decided_by,
        decided_at=utc(case.decided_at) if case.decided_at else None,
        flow_run_id=case.flow_run_id
        or (intake.langflow_job_id if intake and intake.state == "succeeded" else None),
        ruleset_version=case.ruleset_version,
        audit_events=[
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor": event.actor,
                "detail": event.detail,
                "occurred_at": utc(event.occurred_at),
            }
            for event in events
        ],
        current_document_version_id=case.current_document_version_id,
        assessment_id=case.assessment_id,
        row_version=case.row_version,
        hash_kind=version.hash_kind if version else "synthetic_text",
        decision_id=decision.id if decision else None,
        jobs=[job_out(job) for job in jobs],
        reports=[report_out(report) for report in reports],
        parsed_sections=_loads(version.parsed_sections_json) if version else [],
        redacted_sections=_loads(version.redacted_sections_json) if version else [],
        source={
            "source_sha256": version.source_sha256,
            "hash_kind": version.hash_kind,
            "bytes": version.bytes,
            "mime_type": version.mime_type,
            "source_kind": case.source_kind,
            "legacy_flow_label": case.legacy_flow_label,
            "langflow_job_id": intake.langflow_job_id if intake else None,
            "flow_id": intake.flow_id if intake else None,
            "flow_hash": intake.flow_hash if intake else None,
        }
        if version
        else None,
    )


def _require_key(key: str | None) -> str:
    if key is None or not 8 <= len(key.strip()) <= 160:
        raise WorkflowError(
            "idempotency_key_required", "Idempotency-Key must contain 8-160 characters", 422
        )
    return key.strip()


def _service_auth(token: str | None) -> None:
    expected = os.getenv("REVIEW_SERVICE_TOKEN", "synthetic-demo-service-token")
    if not token or not hmac.compare_digest(token, expected):
        raise WorkflowError("service_token_invalid", "Invalid service token", 401)


@app.get("/api/health")
def health(session: SessionDep) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "data_mode": "synthetic-only", "workflow_engine": "Langflow"}


@app.get("/api/system/status")
def system_status(session: SessionDep) -> dict[str, Any]:
    now = datetime.now(UTC)
    if (
        _probe_cache
        and (now - datetime.fromisoformat(_probe_cache["checked_at"])).total_seconds() < 5
    ):
        return _probe_cache
    at = now.isoformat()
    services: dict[str, Any] = {
        "api": {"state": "healthy", "checked_at": at, "detail": "This API request completed"}
    }
    try:
        session.execute(text("SELECT 1"))
        services["database"] = {
            "state": "healthy",
            "checked_at": at,
            "detail": "SELECT 1 completed",
        }
        heartbeat = session.scalar(select(WorkerHeartbeat).order_by(WorkerHeartbeat.seen_at.desc()))
        state = (
            "unknown"
            if heartbeat is None
            else "healthy"
            if (now - utc(heartbeat.seen_at)).total_seconds() < 45
            else "unavailable"
        )
        services["worker"] = {
            "state": state,
            "checked_at": at,
            "detail": "No heartbeat observed"
            if heartbeat is None
            else f"Last heartbeat: {utc(heartbeat.seen_at).isoformat()}",
        }
    except SQLAlchemyError:
        session.rollback()
        services["database"] = {
            "state": "unavailable",
            "checked_at": at,
            "detail": "Database probe failed",
        }
        services["worker"] = {
            "state": "unknown",
            "checked_at": at,
            "detail": "Heartbeat cannot be queried",
        }
    try:
        flow_configuration("intake")
        response = httpx.get(
            os.getenv("LANGFLOW_URL", "http://localhost:7860").rstrip("/") + "/health", timeout=1.5
        )
        services["langflow"] = {
            "state": "healthy" if response.is_success else "degraded",
            "checked_at": at,
            "detail": f"Health probe HTTP {response.status_code}",
        }
    except LangflowError:
        services["langflow"] = {
            "state": "unknown",
            "checked_at": at,
            "detail": "Trusted flows are not configured",
        }
    except httpx.HTTPError:
        services["langflow"] = {
            "state": "unavailable",
            "checked_at": at,
            "detail": "Health probe failed",
        }
    _probe_cache.clear()
    _probe_cache.update({"checked_at": at, "services": services})
    return _probe_cache


@app.get("/api/summary", response_model=DashboardSummary)
def summary(session: SessionDep) -> DashboardSummary:
    cases = session.scalars(select(ReviewCase)).all()
    scored = [
        case for case in cases if case.assessment_id is not None and case.risk_score is not None
    ]
    risk_distribution = {level: 0 for level in ("low", "medium", "high", "critical")}
    category_distribution = {
        category: 0 for category in ("privacy", "legal", "financial", "security", "policy")
    }
    for case in scored:
        risk_distribution[case.risk_level] += 1
        for finding in _loads(case.findings_json):
            category = finding.get("category", "policy")
            category_distribution[category] = category_distribution.get(category, 0) + 1
    probes = _probe_cache.get("services", {})
    return DashboardSummary(
        total_cases=len(cases),
        pending_approval=sum(case.status == "pending_approval" for case in cases),
        high_risk=sum(case.risk_level in {"high", "critical"} for case in scored),
        completed=sum(case.status in DECISIONS for case in cases),
        scored_cases=len(scored),
        average_score=round(sum(case.risk_score for case in scored) / len(scored), 1)
        if scored
        else None,
        risk_distribution=risk_distribution,
        category_distribution=category_distribution,
        system_status={
            name: probes.get(name, {}).get("state", "unknown")
            for name in ("api", "database", "worker", "langflow")
        },
        ruleset_version="2026.10.1",
    )


@app.get("/api/cases", response_model=list[CaseSummary])
def list_cases(
    session: SessionDep,
    status: str | None = None,
    risk_level: str | None = None,
    search: str | None = Query(default=None, max_length=80),
) -> list[CaseSummary]:
    query = select(ReviewCase).order_by(ReviewCase.submitted_at.desc())
    if status:
        query = query.where(ReviewCase.status == status)
    if risk_level:
        query = query.where(ReviewCase.risk_level == risk_level)
    if search:
        query = query.where(ReviewCase.title.contains(search, autoescape=True))
    return [_case_summary(case) for case in session.scalars(query).all()]


@app.post("/api/cases", status_code=202)
async def upload_case(
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "",
    synthetic_confirmed: Annotated[bool, Form()] = False,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    key = _require_key(idempotency_key)
    if not synthetic_confirmed:
        raise WorkflowError(
            "synthetic_confirmation_required", "Confirm that this is a synthetic document", 422
        )
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in MIME_TYPES or len(filename) > 180:
        raise WorkflowError(
            "unsupported_type", "Only PDF, DOCX, TXT and Markdown are supported", 415
        )
    title = title.strip() or Path(filename).stem
    if not 1 <= len(title) <= 180:
        raise WorkflowError("title_invalid", "Title must contain 1-180 characters", 422)
    data = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if len(data) > MAX_FILE_BYTES:
        raise WorkflowError("file_too_large", "Document exceeds the 10 MiB limit", 413)
    validate_document_bytes(data, f".{extension}")
    source_sha = hashlib.sha256(data).hexdigest()
    request_hash = content_hash(
        {
            "source_sha256": source_sha,
            "title": title,
            "extension": extension,
            "synthetic_confirmed": True,
        }
    )
    previous = session.get(UploadRequest, key)
    if previous:
        if previous.request_hash != request_hash:
            raise WorkflowError("idempotency_conflict", "This key was used for different content")
        case = session.get(ReviewCase, previous.case_id)
        return {
            "case_id": case.id,
            "document_version_id": case.current_document_version_id,
            "job_id": previous.job_id,
            "status": case.status,
            "request_id": request.state.request_id,
            "duplicate": True,
        }
    flow_configuration("intake")
    ensure_queue_capacity(session)
    duplicate = session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.source_sha256 == source_sha)
        .order_by(DocumentVersion.created_at)
    )
    case_id, version_id = new_id("RC"), new_id("DV")
    try:
        storage_key = save_document(version_id, extension, data)
    except ValueError as exc:
        raise WorkflowError(
            "runtime_storage_threshold",
            "Runtime storage threshold reached; inventory is required",
            507,
        ) from exc
    now = datetime.now(UTC)
    case = ReviewCase(
        id=case_id,
        title=title,
        document_name=filename,
        document_type=extension.upper(),
        document_hash=source_sha,
        status="received",
        risk_score=None,
        risk_level=None,
        owner="演示提交者",
        submitted_at=now,
        due_at=now + timedelta(hours=24),
        original_text="",
        redacted_text="",
        findings_json="[]",
        dimensions_json="{}",
        warnings_json="[]",
        pii_count=0,
        flow_run_id=None,
        source_kind="uploaded_demo",
        current_document_version_id=version_id,
        row_version=1,
    )
    session.add(case)
    session.flush()
    version = DocumentVersion(
        id=version_id,
        case_id=case_id,
        version_number=1,
        source_sha256=source_sha,
        hash_kind="source_bytes_sha256",
        storage_key=storage_key,
        mime_type=MIME_TYPES[extension],
        bytes=len(data),
    )
    session.add(version)
    session.flush()
    job = create_job(
        session,
        kind="intake",
        case_id=case_id,
        version_id=version_id,
        payload=intake_payload(version),
        dedupe_key=f"intake:{version_id}:0",
    )
    session.flush()
    session.add(UploadRequest(key=key, request_hash=request_hash, case_id=case_id, job_id=job.id))
    audit(
        session,
        case_id,
        "document_received",
        "接收虚构文档；字节指纹已固定，等待真实 Intake。",
        version_id=version_id,
        job_id=job.id,
        request_id=request.state.request_id,
        dedupe_key=f"upload:{version_id}",
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        previous = session.get(UploadRequest, key)
        if previous and previous.request_hash == request_hash:
            existing_case = session.get(ReviewCase, previous.case_id)
            return {
                "case_id": previous.case_id,
                "document_version_id": existing_case.current_document_version_id,
                "job_id": previous.job_id,
                "status": existing_case.status,
                "request_id": request.state.request_id,
                "duplicate": True,
            }
        raise WorkflowError("idempotency_conflict", "A concurrent upload used this key") from exc
    return {
        "case_id": case_id,
        "document_version_id": version_id,
        "job_id": job.id,
        "status": "received",
        "request_id": request.state.request_id,
        "duplicate_of": duplicate.case_id if duplicate else None,
    }


@app.get("/api/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, session: SessionDep) -> CaseDetail:
    case = session.get(ReviewCase, case_id)
    if case is None:
        raise WorkflowError("case_not_found", "Review case not found", 404)
    return _case_detail(session, case)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, session: SessionDep) -> dict[str, Any]:
    job = session.get(WorkflowJob, job_id)
    if job is None:
        raise WorkflowError("job_not_found", "Workflow job not found", 404)
    return job_out(job)


@app.post("/api/cases/{case_id}/decision", response_model=CaseDetail)
def decide_case(
    case_id: str,
    payload: DecisionRequest,
    request: Request,
    session: SessionDep,
    x_reviewer: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> CaseDetail:
    reviewer = (x_reviewer or "").strip()
    if not 1 <= len(reviewer) <= 80:
        raise WorkflowError("reviewer_required", "A non-empty demo reviewer is required", 400)
    try:
        case = record_decision(
            session, case_id, payload, reviewer, idempotency_key, request.state.request_id
        )
    except IntegrityError as exc:
        session.rollback()
        raise WorkflowError(
            "decision_conflict", "A decision already exists for this version"
        ) from exc
    return _case_detail(session, case)


@app.post("/api/cases/{case_id}/retry", status_code=202)
def retry_case(
    case_id: str,
    payload: RetryRequest,
    request: Request,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    key = _require_key(idempotency_key)
    existing = session.scalar(
        select(WorkflowJob).where(WorkflowJob.dedupe_key == f"manual-intake:{case_id}:{key}")
    )
    if existing:
        fixed = json.loads(existing.payload_json)
        if (
            existing.document_version_id != payload.document_version_id
            or fixed.get("retry_of") != payload.job_id
        ):
            raise WorkflowError(
                "idempotency_conflict", "This retry key was used for another request"
            )
        return job_out(existing)
    case = session.scalar(select(ReviewCase).where(ReviewCase.id == case_id).with_for_update())
    prior = session.get(WorkflowJob, payload.job_id)
    if case is None or prior is None or prior.case_id != case_id:
        raise WorkflowError("case_not_found", "Case or job not found", 404)
    if (
        case.decision
        or case.status != "failed"
        or case.current_document_version_id != payload.document_version_id
        or prior.document_version_id != case.current_document_version_id
        or prior.kind != "intake"
        or prior.state != "failed"
    ):
        raise WorkflowError(
            "retry_not_allowed", "Only an active failed, undecided intake can be retried"
        )
    history = session.scalars(
        select(WorkflowJob).where(
            WorkflowJob.case_id == case_id,
            WorkflowJob.document_version_id == case.current_document_version_id,
            WorkflowJob.kind == "intake",
        )
    ).all()
    latest = max(history, key=lambda job: (job.retry_generation, job.created_at, job.id))
    if latest.id != prior.id:
        raise WorkflowError("retry_not_allowed", "Only the latest failed intake can be retried")
    generation = max(job.retry_generation for job in history) + 1
    if generation > 3:
        raise WorkflowError(
            "retry_limit_reached", "Manual retry limit reached; inspect the diagnostic"
        )
    version = session.get(DocumentVersion, payload.document_version_id)
    job = create_job(
        session,
        kind="intake",
        case_id=case_id,
        version_id=version.id,
        payload={**intake_payload(version), "retry_of": prior.id},
        dedupe_key=f"manual-intake:{case_id}:{key}",
        retry_generation=generation,
    )
    case.status, case.row_version = "received", case.row_version + 1
    audit(
        session,
        case_id,
        "intake_retry_requested",
        "请求新一代 Intake 重试；原失败记录保留。",
        version_id=version.id,
        job_id=job.id,
        request_id=request.state.request_id,
        dedupe_key=job.dedupe_key,
    )
    session.commit()
    return job_out(job)


@app.post("/api/integrations/langflow/results")
def accept_intake(
    payload: IntakeResult,
    request: Request,
    session: SessionDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _service_auth(x_service_token)
    try:
        return persist_intake(session, payload, request.state.request_id)
    except IntegrityError as exc:
        session.rollback()
        job = session.get(WorkflowJob, payload.job_id)
        if (
            job
            and job.execution_token == payload.execution_token
            and job.result_hash == content_hash(payload.model_dump())
        ):
            return {"accepted": True, "duplicate": True}
        raise WorkflowError("callback_result_conflict", "Concurrent result conflict") from exc


@app.post("/api/integrations/langflow/reports")
def accept_reports(
    payload: ReportResult,
    request: Request,
    session: SessionDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _service_auth(x_service_token)
    return persist_reports(session, payload, request.state.request_id)


@app.post("/api/integrations/langflow/tasks")
def legacy_task_gateway(
    payload: LangflowTaskRequest,
    session: SessionDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _service_auth(x_service_token)
    if session.get(ReviewCase, payload.case_id) is None:
        raise WorkflowError("case_not_found", "No case exists for this legacy request", 404)
    raise WorkflowError(
        "legacy_callback_incomplete", "Use /results with the full bound intake envelope", 422
    )


@app.post("/api/integrations/langflow/jobs/{job_id}/failure")
def job_failure(
    job_id: str,
    payload: dict[str, Any],
    request: Request,
    session: SessionDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _service_auth(x_service_token)
    job = session.scalar(select(WorkflowJob).where(WorkflowJob.id == job_id).with_for_update())
    if job is None:
        raise WorkflowError("job_not_found", "Workflow job not found", 404)
    if (
        payload.get("execution_token") != job.execution_token
        or payload.get("attempt") != job.attempt
    ):
        raise WorkflowError("job_attempt_conflict", "Failure notification is from an older attempt")
    if job.state != "failed":
        return {"accepted": True, "state": job.state}
    dedupe_key = f"failed:{job.id}:{job.attempt}"
    if session.scalar(select(AuditEvent.id).where(AuditEvent.dedupe_key == dedupe_key)):
        return {"accepted": True, "state": "failed", "duplicate": True}
    case = session.scalar(select(ReviewCase).where(ReviewCase.id == job.case_id).with_for_update())
    if (
        job.kind == "intake"
        and not case.decision
        and case.current_document_version_id == job.document_version_id
    ):
        case.status, case.risk_score, case.risk_level, case.assessment_id = (
            "failed",
            None,
            None,
            None,
        )
        case.row_version += 1
    if job.kind == "report":
        for artifact in session.scalars(
            select(ReportArtifact).where(
                ReportArtifact.generation_job_id == job.id, ReportArtifact.state != "ready"
            )
        ):
            artifact.state, artifact.error_code = "failed", job.error_code
    audit(
        session,
        case.id,
        "intake_failed" if job.kind == "intake" else "report_failed",
        f"后台任务失败：{job.error_code or 'unknown'}。已记录人工决定不会撤销。",
        job_id=job.id,
        version_id=job.document_version_id,
        request_id=request.state.request_id,
        dedupe_key=dedupe_key,
    )
    session.commit()
    return {"accepted": True, "state": "failed"}


@app.post("/api/integrations/langflow/jobs/{job_id}/started")
def job_started(
    job_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    x_service_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    _service_auth(x_service_token)
    job = session.scalar(select(WorkflowJob).where(WorkflowJob.id == job_id).with_for_update())
    if job is None:
        raise WorkflowError("job_not_found", "Workflow job not found", 404)
    if (
        payload.get("execution_token") != job.execution_token
        or payload.get("attempt") != job.attempt
    ):
        raise WorkflowError("job_attempt_conflict", "Start notification is from an older attempt")
    if job.state != "running":
        return {"accepted": True, "state": job.state}
    case = session.scalar(select(ReviewCase).where(ReviewCase.id == job.case_id).with_for_update())
    if (
        job.kind == "intake"
        and case.current_document_version_id == job.document_version_id
        and not case.decision
        and case.status == "received"
    ):
        case.status = "processing"
    if job.kind == "report":
        for artifact in session.scalars(
            select(ReportArtifact).where(
                ReportArtifact.generation_job_id == job.id, ReportArtifact.state == "queued"
            )
        ):
            artifact.state = "processing"
    session.commit()
    return {"accepted": True, "state": job.state}


@app.get("/api/cases/{case_id}/reports")
def list_reports(case_id: str, session: SessionDep) -> list[dict[str, Any]]:
    if session.get(ReviewCase, case_id) is None:
        raise WorkflowError("case_not_found", "Review case not found", 404)
    return [
        report_out(report)
        for report in session.scalars(
            select(ReportArtifact).where(ReportArtifact.case_id == case_id)
        )
    ]


@app.post("/api/cases/{case_id}/reports/retry", status_code=202)
def retry_reports(
    case_id: str,
    payload: ReportRetryRequest,
    request: Request,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    key = _require_key(idempotency_key)
    dedupe = f"manual-report:{case_id}:{key}"
    existing = session.scalar(select(WorkflowJob).where(WorkflowJob.dedupe_key == dedupe))
    if existing:
        previous = json.loads(existing.payload_json)
        if previous["snapshot"]["snapshot_hash"] != payload.snapshot_hash or set(
            previous["formats"]
        ) != set(payload.formats):
            raise WorkflowError(
                "idempotency_conflict", "This retry key was used for another report request"
            )
        return job_out(existing)
    decision = session.scalar(
        select(Decision)
        .where(Decision.case_id == case_id, Decision.snapshot_hash == payload.snapshot_hash)
        .with_for_update()
    )
    if decision is None or decision.decision not in DECISIONS:
        raise WorkflowError("decision_snapshot_missing", "A saved human decision is required")
    artifacts = session.scalars(
        select(ReportArtifact).where(ReportArtifact.snapshot_hash == payload.snapshot_hash)
    ).all()
    selected = [artifact for artifact in artifacts if artifact.format in payload.formats]
    if len(selected) != len(set(payload.formats)) or any(
        artifact.state not in {"failed", "missing"} for artifact in selected
    ):
        raise WorkflowError(
            "report_retry_not_allowed", "Only failed or missing formats can be regenerated"
        )
    prior_jobs = session.scalars(
        select(WorkflowJob).where(WorkflowJob.decision_id == decision.id)
    ).all()
    generation = max((job.retry_generation for job in prior_jobs), default=0) + 1
    if generation > 3:
        raise WorkflowError(
            "retry_limit_reached", "Manual retry limit reached; inspect the diagnostic"
        )
    if any(job.state in {"queued", "running", "retry_wait"} for job in prior_jobs):
        raise WorkflowError("report_job_active", "A report job is already active")
    job = create_job(
        session,
        kind="report",
        case_id=case_id,
        version_id=decision.document_version_id,
        decision_id=decision.id,
        payload={
            "snapshot": json.loads(decision.snapshot_json),
            "formats": sorted(set(payload.formats)),
            "decision_id": decision.id,
        },
        dedupe_key=dedupe,
        retry_generation=generation,
    )
    session.flush()
    for artifact in selected:
        artifact.state, artifact.error_code, artifact.generation_job_id = "queued", None, job.id
    audit(
        session,
        case_id,
        "report_retry_requested",
        "只重试失败或缺失的报告格式；现有报告与决定保持不变。",
        decision_id=decision.id,
        job_id=job.id,
        request_id=request.state.request_id,
        dedupe_key=dedupe,
    )
    session.commit()
    return job_out(job)


@app.get("/api/cases/{case_id}/report/{report_format}")
def export_report(
    case_id: str, report_format: str, session: SessionDep, report_id: str | None = None
) -> Response:
    case = session.get(ReviewCase, case_id)
    if case is None:
        raise WorkflowError("case_not_found", "Review case not found", 404)
    if report_format not in FORMATS:
        raise WorkflowError("report_format_unsupported", "Unsupported report format", 404)
    if case.status not in DECISIONS or not case.decision:
        raise WorkflowError(
            "human_decision_required", "A valid human decision is required before export"
        )
    query = select(ReportArtifact).where(
        ReportArtifact.case_id == case_id, ReportArtifact.format == report_format
    )
    query = (
        query.where(ReportArtifact.id == report_id)
        if report_id
        else query.where(ReportArtifact.document_version_id == case.current_document_version_id)
    )
    artifact = session.scalar(query)
    if artifact is None or artifact.state != "ready" or not artifact.storage_key:
        raise WorkflowError("report_not_ready", "The report is not ready for download")
    decision = session.get(Decision, artifact.decision_id)
    if (
        decision is None
        or decision.decision not in DECISIONS
        or decision.snapshot_hash != artifact.snapshot_hash
    ):
        raise WorkflowError(
            "report_snapshot_invalid", "Report does not match the saved human decision"
        )
    try:
        data = resolve_storage(reports_root(), artifact.storage_key).read_bytes()
    except (OSError, ValueError) as exc:
        raise WorkflowError("report_file_missing", "Registered report bytes are missing") from exc
    if len(data) != artifact.bytes or hashlib.sha256(data).hexdigest() != artifact.sha256:
        raise WorkflowError("report_integrity_invalid", "Report failed byte-integrity verification")
    return Response(
        data,
        media_type={
            "json": "application/json",
            "html": "text/html; charset=utf-8",
            "pdf": "application/pdf",
        }[report_format],
        headers={
            "Content-Disposition": f'attachment; filename="{case_id}-report.{report_format}"',
            "X-Content-SHA256": artifact.sha256,
        },
    )
