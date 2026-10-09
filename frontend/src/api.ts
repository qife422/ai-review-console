import type { AcceptedTask, CaseDetail, CaseSummary, DashboardSummary, Decision, ReportFormat, SystemStatus, WorkflowJob } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null,
    public readonly retryable: boolean,
  ) { super(message); }
}

async function responseRequest(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { code?: string; detail?: unknown; request_id?: string; retryable?: boolean } | null;
    const detail = typeof payload?.detail === "string" ? payload.detail : `请求失败 (${response.status})`;
    throw new ApiError(detail, response.status, payload?.code ?? "request_failed", payload?.request_id ?? null, payload?.retryable ?? false);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await responseRequest(path, init)).json() as Promise<T>;
}

export const api = {
  summary: (signal?: AbortSignal) => request<DashboardSummary>("/summary", { signal }),
  cases: (signal?: AbortSignal) => request<CaseSummary[]>("/cases", { signal }),
  case: (caseId: string, signal?: AbortSignal) => request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`, { signal }),
  systemStatus: (signal?: AbortSignal) => request<SystemStatus>("/system/status", { signal }),
  upload: (file: File, title: string, idempotencyKey: string, signal?: AbortSignal) => {
    const body = new FormData();
    body.append("file", file);
    body.append("title", title.trim());
    body.append("synthetic_confirmed", "true");
    return request<AcceptedTask>("/cases", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body, signal });
  },
  decide: (detail: CaseDetail, decision: Decision, reason: string, reviewer: string, idempotencyKey: string, signal?: AbortSignal) =>
    request<CaseDetail>(`/cases/${encodeURIComponent(detail.id)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Reviewer": reviewer, "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ decision, reason: reason.trim(), document_version_id: detail.current_document_version_id, assessment_id: detail.assessment_id, expected_row_version: detail.row_version }),
      signal,
    }),
  retry: (detail: CaseDetail, jobId: string, idempotencyKey: string, signal?: AbortSignal) =>
    request<WorkflowJob>(`/cases/${encodeURIComponent(detail.id)}/retry`, {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ document_version_id: detail.current_document_version_id, job_id: jobId }), signal,
    }),
  retryReports: (caseId: string, snapshotHash: string, formats: ReportFormat[], idempotencyKey: string, signal?: AbortSignal) =>
    request<WorkflowJob>(`/cases/${encodeURIComponent(caseId)}/reports/retry`, {
      method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ snapshot_hash: snapshotHash, formats }), signal,
    }),
  reportUrl: (caseId: string, format: ReportFormat, reportId?: string) =>
    `${API_BASE}/cases/${encodeURIComponent(caseId)}/report/${format}${reportId ? `?report_id=${encodeURIComponent(reportId)}` : ""}`,
  downloadReport: async (caseId: string, format: ReportFormat, reportId: string, signal?: AbortSignal) =>
    (await responseRequest(`/cases/${encodeURIComponent(caseId)}/report/${format}?report_id=${encodeURIComponent(reportId)}`, { signal })).blob(),
};
