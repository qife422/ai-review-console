import type { CaseDetail, DashboardSummary, SystemStatus } from "../types";

export const testSummary: DashboardSummary = {
  total_cases: 1, pending_approval: 1, high_risk: 1, completed: 0, average_score: 57, scored_cases: 1,
  risk_distribution: { low: 0, medium: 0, high: 1, critical: 0 },
  category_distribution: { privacy: 1, legal: 1, financial: 0, security: 0, policy: 0 },
  system_status: { api: "healthy", database: "healthy", worker: "healthy", langflow: "healthy" }, ruleset_version: "2026.09-demo.1",
};

export const testSystemStatus: SystemStatus = {
  checked_at: "2026-10-08T12:00:00Z",
  services: { api: { state: "healthy", checked_at: "2026-10-08T12:00:00Z" }, database: { state: "healthy", checked_at: "2026-10-08T12:00:00Z" }, worker: { state: "healthy", checked_at: "2026-10-08T12:00:00Z" }, langflow: { state: "unavailable", checked_at: "2026-10-08T12:00:00Z", detail: "未取得上游响应" } },
};

export function makeDetail(overrides: Partial<CaseDetail> = {}): CaseDetail {
  return {
    id: "RC-TEST", title: "虚构协议", document_name: "synthetic.txt", document_type: "TXT", status: "pending_approval",
    risk_score: 57, risk_level: "high", owner: "林澈", submitted_at: "2026-10-08T12:00:00Z", due_at: "2026-10-09T12:00:00Z", pii_count: 1, decision: null,
    source_kind: "uploaded_demo", current_document_version_id: "version-1", assessment_id: "assessment-1", row_version: 3,
    document_hash: "a".repeat(64), hash_kind: "source_bytes_sha256", original_text: "SYNTHETIC DEMO DOCUMENT\n承担全部损失。", redacted_text: "SYNTHETIC DEMO DOCUMENT\n承担全部损失。",
    findings: [{ rule_id: "LEGAL-002", category: "legal", title: "责任上限缺失", severity: "critical", points: 28, evidence: "承担全部损失。", recommendation: "补充责任上限。", section_id: "section-1", locator: "block:1", start: 0, end: 7, offset_basis: "redacted_unicode_codepoints" }],
    dimensions: { legal: 84 }, warnings: [], decision_reason: null, decided_by: null, decided_at: null,
    flow_run_id: "upstream-run-1", ruleset_version: "2026.09-demo.1", audit_events: [],
    jobs: [{ job_id: "job-intake-1", kind: "intake", state: "succeeded", phase: "completed", attempt: 1, error_code: null, retryable: false, langflow_job_id: "upstream-run-1" }], reports: [],
    parsed_sections: [{ section_id: "section-1", locator: "block:1", text: "SYNTHETIC DEMO DOCUMENT\n承担全部损失。" }], redacted_sections: [{ section_id: "section-1", locator: "block:1", text: "SYNTHETIC DEMO DOCUMENT\n承担全部损失。" }],
    source: { source_sha256: "a".repeat(64), hash_kind: "source_bytes_sha256", bytes: 200, mime_type: "text/plain", source_kind: "uploaded_demo", legacy_flow_label: null, langflow_job_id: "upstream-run-1", flow_id: "intake-flow", flow_hash: "b".repeat(64) },
    ...overrides,
  };
}

export function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}
