export type RiskLevel = "low" | "medium" | "high" | "critical";
export type Decision = "approved" | "rejected" | "changes_requested";
export type ReportFormat = "json" | "html" | "pdf";
export type SourceKind = "seed_demo" | "uploaded_demo";
export type JobState = "queued" | "running" | "retry_wait" | "succeeded" | "failed";
export type ServiceState = "healthy" | "degraded" | "unavailable" | "unknown";

export interface CaseSummary {
  id: string;
  title: string;
  document_name: string;
  document_type: string;
  status: string;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  owner: string;
  submitted_at: string;
  due_at: string;
  pii_count: number;
  decision: Decision | null;
  source_kind?: SourceKind;
  current_document_version_id?: string | null;
  row_version?: number;
}

export interface Finding {
  rule_id: string;
  category: string;
  title: string;
  severity: string;
  points: number;
  evidence: string;
  recommendation: string;
  section_id?: string | null;
  locator?: string | null;
  start?: number | null;
  end?: number | null;
  offset_basis?: string | null;
}

export interface DocumentSection {
  section_id: string;
  locator: string;
  text: string;
  index?: number;
}

export interface WorkflowJob {
  job_id: string;
  kind: "intake" | "report";
  state: JobState;
  phase: string;
  attempt: number;
  retry_generation?: number;
  error_code: string | null;
  error_detail?: string | null;
  retryable: boolean;
  langflow_job_id?: string | null;
  flow_id?: string | null;
  flow_hash?: string | null;
  next_run_at?: string | null;
  created_at?: string;
}

export interface ReportArtifact {
  report_id: string;
  format: ReportFormat;
  state: "queued" | "processing" | "ready" | "failed" | "missing" | "previous_version";
  snapshot_hash: string;
  sha256: string | null;
  bytes: number | null;
  created_at: string | null;
  error_code?: string | null;
  download_url?: string | null;
}

export interface DocumentSource {
  source_sha256: string | null;
  hash_kind: string;
  bytes: number | null;
  mime_type: string | null;
  source_kind: SourceKind;
  legacy_flow_label: string | null;
  langflow_job_id: string | null;
  flow_id: string | null;
  flow_hash: string | null;
}

export interface AuditEvent {
  id: number;
  event_type: string;
  actor: string;
  detail: string;
  occurred_at: string;
}

export interface CaseDetail extends CaseSummary {
  document_hash: string;
  original_text: string;
  redacted_text: string;
  findings: Finding[];
  dimensions: Record<string, number>;
  warnings: string[];
  decision_reason: string | null;
  decided_by: string | null;
  decided_at: string | null;
  flow_run_id: string | null;
  ruleset_version: string;
  audit_events: AuditEvent[];
  current_document_version_id: string | null;
  assessment_id: string | null;
  row_version: number;
  source_kind: SourceKind;
  hash_kind: string;
  jobs: WorkflowJob[];
  reports: ReportArtifact[];
  parsed_sections: DocumentSection[];
  redacted_sections: DocumentSection[];
  source: DocumentSource | null;
  decision_id?: string | null;
}

export interface DashboardSummary {
  total_cases: number;
  pending_approval: number;
  high_risk: number;
  completed: number;
  average_score: number | null;
  scored_cases?: number;
  risk_distribution: Record<RiskLevel, number>;
  category_distribution: Record<string, number>;
  system_status: Record<string, string>;
  ruleset_version: string;
}

export interface SystemStatus {
  checked_at: string;
  services: Record<string, { state: ServiceState; checked_at: string | null; detail?: string | null }>;
}

export interface AcceptedTask {
  case_id: string;
  document_version_id: string;
  job_id: string;
  status: string;
  request_id?: string;
  duplicate_of?: string | null;
}
