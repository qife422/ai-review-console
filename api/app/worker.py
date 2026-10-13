"""One bounded worker backed by durable PostgreSQL jobs and renewable leases."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import and_, or_, select, update

from .database import SessionLocal, engine
from .langflow_client import LangflowClient, LangflowError, event_error, output_objects
from .migrations import require_schema
from .models import ReportArtifact, WorkerHeartbeat, WorkflowJob

LOGGER = logging.getLogger("review.worker")
LEASE_SECONDS = 90
EXECUTION_SECONDS = 120
RETRY_DELAYS = (10, 30)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class Worker:
    def __init__(self, worker_id: str | None = None):
        self.id = worker_id or f"worker-{uuid.uuid4().hex[:16]}"
        self.stopping = False
        self.langflow = LangflowClient()
        self.api = httpx.Client(
            base_url=os.getenv("REVIEW_API_URL", "http://api:8000").rstrip("/"),
            timeout=20,
            headers={"X-Service-Token": os.getenv("REVIEW_SERVICE_TOKEN", "")},
        )

    def heartbeat(self) -> None:
        with SessionLocal.begin() as session:
            item = session.get(WorkerHeartbeat, self.id)
            if item:
                item.seen_at = datetime.now(UTC)
            else:
                session.add(WorkerHeartbeat(id=self.id, seen_at=datetime.now(UTC)))

    def claim(self) -> WorkflowJob | None:
        now = datetime.now(UTC)
        eligible = or_(
            and_(WorkflowJob.state.in_(["queued", "retry_wait"]), WorkflowJob.next_run_at <= now),
            and_(WorkflowJob.state == "running", WorkflowJob.lease_until < now),
        )
        with SessionLocal.begin() as session:
            job = session.scalar(
                select(WorkflowJob)
                .where(eligible)
                .order_by(WorkflowJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            recovered = job.state == "running"
            lease_token = uuid.uuid4().hex
            values: dict[str, Any] = {
                "state": "running",
                "phase": "recovering" if recovered else "starting",
                "lease_owner": self.id,
                "lease_token": lease_token,
                "lease_until": now + timedelta(seconds=LEASE_SECONDS),
                "error_code": None,
                "error_detail": None,
            }
            if not recovered:
                values.update(
                    attempt=job.attempt + 1, execution_token=uuid.uuid4().hex, langflow_job_id=None
                )
                if hasattr(WorkflowJob, "execution_started_at"):
                    values["execution_started_at"] = now
            # The CAS also protects SQLite unit tests, whose FOR UPDATE is a no-op.
            changed = session.execute(
                update(WorkflowJob)
                .where(
                    WorkflowJob.id == job.id,
                    eligible,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            ).rowcount
            if changed != 1:
                return None
            session.refresh(job)
            session.expunge(job)
            return job

    def renew(self, job: WorkflowJob, phase: str | None = None) -> bool:
        now = datetime.now(UTC)
        values: dict[str, Any] = {"lease_until": now + timedelta(seconds=LEASE_SECONDS)}
        if phase:
            values["phase"] = phase
        with SessionLocal.begin() as session:
            changed = session.execute(
                update(WorkflowJob)
                .where(
                    WorkflowJob.id == job.id,
                    WorkflowJob.lease_owner == self.id,
                    WorkflowJob.lease_token == job.lease_token,
                    WorkflowJob.state == "running",
                )
                .values(**values)
            ).rowcount
        self.heartbeat()
        return changed == 1

    def _state(self, job_id: str) -> str | None:
        with SessionLocal() as session:
            item = session.get(WorkflowJob, job_id)
            return item.state if item else None

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.api.post(endpoint, json=payload)
        except httpx.HTTPError as exc:
            raise LangflowError(
                "callback_unavailable", "Review API connection failed", True
            ) from exc
        if response.is_error:
            code = "callback_validation_failed"
            retryable = response.status_code == 429 or response.status_code >= 500
            with suppress(ValueError, AttributeError):
                body = response.json()
                code = body.get("code", code)
                retryable = retryable or body.get("retryable") is True
            if response.status_code in {401, 403, 422}:
                retryable = False
            raise LangflowError(
                code,
                f"Review API returned HTTP {response.status_code}",
                retryable,
            )
        result = response.json()
        if not isinstance(result, dict) or not result.get("accepted"):
            raise LangflowError("callback_not_persisted", "Review API did not persist the result")
        return result

    def _runtime(self, job: WorkflowJob) -> dict[str, Any]:
        payload = json.loads(job.payload_json)
        payload.update(
            {
                "case_id": job.case_id,
                "document_version_id": job.document_version_id,
                "job_id": job.id,
                "execution_token": job.execution_token,
                "payload_hash": job.payload_hash,
                "flow_id": job.flow_id,
                "flow_hash": job.flow_hash,
                "config_hash": job.config_hash,
            }
        )
        if job.kind == "report":
            payload["decision_id"] = job.decision_id
            with SessionLocal() as session:
                ready = set(
                    session.scalars(
                        select(ReportArtifact.format).where(
                            ReportArtifact.decision_id == job.decision_id,
                            ReportArtifact.state == "ready",
                        )
                    ).all()
                )
            payload["formats"] = [
                item
                for item in payload.get("formats", ["json", "html", "pdf"])
                if item not in ready
            ]
        return payload

    def _report_reconcile(self, job: WorkflowJob, runtime: dict[str, Any]) -> dict[str, Any] | None:
        """Recover a lost end-vertex event from immutable, version-bound files.

        Existence alone never changes business state: the API verifies every byte
        hash and all snapshot references before registering any artifact.
        """
        snapshot_hash = runtime["snapshot"]["snapshot_hash"]
        root = Path(os.getenv("REPORT_STORAGE_ROOT", "/app/artifacts")).resolve()
        artifacts = []
        for report_format in runtime["formats"]:
            key = f"{job.decision_id}/{snapshot_hash}/report.{report_format}"
            path = (root / key).resolve()
            if root not in path.parents or not path.is_file():
                continue
            content = path.read_bytes()
            artifacts.append(
                {
                    "format": report_format,
                    "storage_key": key,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                    "template_version": runtime["snapshot"].get("template_version", "2026.10.1"),
                }
            )
        if not artifacts:
            return None
        return {
            **{
                key: runtime[key]
                for key in (
                    "case_id",
                    "document_version_id",
                    "job_id",
                    "execution_token",
                    "payload_hash",
                    "flow_id",
                    "flow_hash",
                    "decision_id",
                )
            },
            "schema_version": "1.0",
            "snapshot_hash": snapshot_hash,
            "artifacts": artifacts,
            "errors": [
                {
                    "format": item,
                    "code": "report_output_missing",
                    "detail": "The Flow did not publish this format",
                    "retryable": True,
                }
                for item in runtime["formats"]
                if item not in {artifact["format"] for artifact in artifacts}
            ],
        }

    def _reconcile_stopped_report(self, job: WorkflowJob, runtime: dict[str, Any]) -> bool:
        """Register recoverable outputs once the upstream run cannot continue."""
        if job.kind != "report":
            return False
        recovered = self._report_reconcile(job, runtime)
        if recovered is None:
            return False
        self._post("/api/integrations/langflow/reports", recovered)
        if self._state(job.id) == "succeeded":
            return True
        if recovered["errors"]:
            raise LangflowError("report_partial", "Some report formats failed", True)
        return False

    def run_job(self, job: WorkflowJob) -> None:
        try:
            self._post(
                f"/api/integrations/langflow/jobs/{job.id}/started",
                {
                    "execution_token": job.execution_token,
                    "attempt": job.attempt,
                },
            )
        except LangflowError as exc:
            if not job.langflow_job_id or not exc.retryable:
                raise
            # A temporary API outage does not invalidate an existing upstream run.
            LOGGER.warning("Start reconciliation pending for job %s", job.id)
        runtime = self._runtime(job)
        if job.kind == "report" and not runtime["formats"]:
            raise LangflowError("report_already_registered", "All requested formats are registered")
        if not job.langflow_job_id:
            upstream_id = self.langflow.start(
                kind=job.kind, flow_id=job.flow_id, flow_hash=job.flow_hash, runtime=runtime
            )
            with SessionLocal.begin() as session:
                changed = session.execute(
                    update(WorkflowJob)
                    .where(
                        WorkflowJob.id == job.id,
                        WorkflowJob.lease_token == job.lease_token,
                        WorkflowJob.execution_token == job.execution_token,
                    )
                    .values(langflow_job_id=upstream_id, phase="processing")
                ).rowcount
                if changed != 1:
                    raise LangflowError("job_lease_lost", "The worker no longer owns this job")
            job.langflow_job_id = upstream_id
        elif job.kind == "report":
            recovered_output = self._report_reconcile(job, runtime)
            if recovered_output and not recovered_output["errors"]:
                self._post("/api/integrations/langflow/reports", recovered_output)
                if self._state(job.id) == "succeeded":
                    return
        start = getattr(job, "execution_started_at", None) or datetime.now(UTC)
        remaining = max(0, EXECUTION_SECONDS - (datetime.now(UTC) - _aware(start)).total_seconds())
        deadline, last_renewal = time.monotonic() + remaining, time.monotonic()
        report_output: dict[str, Any] | None = None
        while not self.stopping and time.monotonic() < deadline:
            if self._state(job.id) == "succeeded":
                return
            if time.monotonic() - last_renewal >= 15:
                if not self.renew(job, "processing"):
                    if self._state(job.id) == "succeeded":
                        return
                    raise LangflowError("job_lease_lost", "The worker no longer owns this job")
                last_renewal = time.monotonic()
            try:
                events = self.langflow.poll(job.langflow_job_id)
            except LangflowError as exc:
                if exc.code == "langflow_not_found":
                    if self._reconcile_stopped_report(job, runtime):
                        return
                    raise LangflowError(
                        "langflow_run_lost", "The upstream run no longer exists", True
                    ) from exc
                if exc.retryable:
                    # Poll the same execution after a transient outage, retaining
                    # its token and job ID. The persisted total deadline is bounded.
                    time.sleep(2)
                    continue
                raise
            terminal = False
            for event in events:
                failure = event_error(event)
                if failure:
                    raise failure
                if event.get("event") == "end_vertex":
                    for output in output_objects(event):
                        if output.get("job_id") == job.id and "artifacts" in output:
                            report_output = output
                terminal |= event.get("event") in {"end", "build_end", "close"}
            if job.kind == "report" and (report_output or terminal):
                report_output = report_output or self._report_reconcile(job, runtime)
                if report_output:
                    self._post("/api/integrations/langflow/reports", report_output)
                    if report_output.get("errors"):
                        raise LangflowError("report_partial", "Some report formats failed", True)
                    if self._state(job.id) == "succeeded":
                        return
            if terminal:
                if self._state(job.id) == "succeeded":
                    return
                raise LangflowError(
                    "result_not_persisted", "Flow ended without a persisted business result", True
                )
            time.sleep(1)
        if self.stopping:
            # Leave the run and token intact. Another process resumes it after lease expiry.
            return
        try:
            self.langflow.cancel(job.langflow_job_id)
        except LangflowError:
            LOGGER.warning("Cancellation unavailable for job %s", job.id)
        if self._reconcile_stopped_report(job, runtime):
            return
        raise LangflowError(
            "workflow_timeout", "Flow exceeded its 120 second execution limit", True
        )

    def record_failure(self, job: WorkflowJob, failure: LangflowError) -> None:
        now = datetime.now(UTC)
        retry = failure.retryable and job.attempt < 3
        with SessionLocal.begin() as session:
            # A successful callback can commit while a failure is being handled.
            # The predicate is evaluated atomically after any row lock wait; an
            # ORM read followed by a write could otherwise overwrite success.
            changed = session.execute(
                update(WorkflowJob)
                .where(
                    WorkflowJob.id == job.id,
                    WorkflowJob.execution_token == job.execution_token,
                    WorkflowJob.lease_token == job.lease_token,
                    WorkflowJob.state != "succeeded",
                )
                .values(
                    state="retry_wait" if retry else "failed",
                    phase="failure_pending",
                    error_code=failure.code,
                    error_detail=failure.detail,
                    next_run_at=(
                        now + timedelta(seconds=RETRY_DELAYS[min(job.attempt - 1, 1)])
                        if retry
                        else now
                    ),
                    lease_until=None,
                    lease_owner=None,
                )
                .execution_options(synchronize_session=False)
            ).rowcount
            if changed != 1:
                return
        try:
            self._post(
                f"/api/integrations/langflow/jobs/{job.id}/failure",
                {
                    "execution_token": job.execution_token,
                    "attempt": job.attempt,
                    "error_code": failure.code,
                    "detail": failure.detail,
                    "retryable": retry,
                },
            )
            with SessionLocal.begin() as session:
                session.execute(
                    update(WorkflowJob)
                    .where(
                        WorkflowJob.id == job.id,
                        WorkflowJob.execution_token == job.execution_token,
                        WorkflowJob.phase == "failure_pending",
                    )
                    .values(phase="retry_wait" if retry else "failed")
                )
        except LangflowError:
            LOGGER.warning("Failure reconciliation pending for job %s", job.id)
        LOGGER.warning(
            "Job %s attempt %s: %s (%s)",
            job.id,
            job.attempt,
            failure.code,
            "retry_wait" if retry else "failed",
        )

    def reconcile_failures(self) -> None:
        with SessionLocal() as session:
            pending = session.scalars(
                select(WorkflowJob)
                .where(
                    WorkflowJob.state == "failed",
                    WorkflowJob.phase == "failure_pending",
                )
                .limit(10)
            ).all()
            for item in pending:
                session.expunge(item)
        for job in pending:
            try:
                self._post(
                    f"/api/integrations/langflow/jobs/{job.id}/failure",
                    {
                        "execution_token": job.execution_token,
                        "attempt": job.attempt,
                        "error_code": job.error_code,
                        "detail": job.error_detail,
                        "retryable": False,
                    },
                )
            except LangflowError:
                return
            with SessionLocal.begin() as session:
                session.execute(
                    update(WorkflowJob)
                    .where(
                        WorkflowJob.id == job.id,
                        WorkflowJob.phase == "failure_pending",
                        WorkflowJob.execution_token == job.execution_token,
                    )
                    .values(phase="failed")
                )

    def run(self) -> None:
        require_schema(engine)
        LOGGER.info("Worker %s started", self.id)
        try:
            while not self.stopping:
                self.heartbeat()
                self.reconcile_failures()
                job = self.claim()
                if job is None:
                    time.sleep(2)
                    continue
                try:
                    self.run_job(job)
                except LangflowError as exc:
                    self.record_failure(job, exc)
                except (ValueError, KeyError, OSError) as exc:
                    LOGGER.exception("Invalid worker input for job %s", job.id)
                    self.record_failure(
                        job, LangflowError("worker_input_invalid", type(exc).__name__)
                    )
        finally:
            self.langflow.close()
            self.api.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    worker = Worker()

    def stop(_signum: int, _frame: object) -> None:
        worker.stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
