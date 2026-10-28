import { ApiError } from "../apiError";
import type { AcceptedTask, CaseDetail, CaseSummary, DashboardSummary, Decision, DocumentSection, Finding, ReportArtifact, ReportFormat, SystemStatus, WorkflowJob } from "../types";

export const DEMO_NOTICE = "SYNTHETIC DEMO DATA ONLY / 浏览器流程模拟，非真实 AI / Langflow 运行，不构成法律意见。";

export interface DemoSample {
  id: string;
  title: string;
  filename: string;
  description: string;
  text: string;
}

interface Scenario extends DemoSample {
  redacted: string;
  points: number;
  pii: number;
  findings: Array<{ category: string; id: string; title: string; severity: string; points: number; evidence: string; recommendation: string }>;
}

const marker = "SYNTHETIC DEMO DOCUMENT\n在线演示预置虚构样本；不包含真实合同或个人资料。\n\n";
const scenarios: readonly Scenario[] = [
  {
    id: "liability", title: "星屿采购协议：责任边界", filename: "synthetic-liability.txt",
    description: "体验责任上限发现、证据定位与要求修改。",
    text: marker + "星屿虚构实验室与松岚虚构商贸约定：供应方承担全部损失，且不设责任上限。\n联系人邮箱：review@example.net。",
    redacted: marker + "星屿虚构实验室与松岚虚构商贸约定：供应方承担全部损失，且不设责任上限。\n联系人邮箱：[EMAIL_01]。",
    points: 28, pii: 1,
    findings: [{ category: "legal", id: "LEGAL-002", title: "责任上限缺失或无限责任", severity: "critical", points: 28, evidence: "供应方承担全部损失，且不设责任上限。", recommendation: "补充与合同金额及过错范围相称的责任上限。" }],
  },
  {
    id: "privacy", title: "岚桥服务协议：隐私与账号", filename: "synthetic-privacy.txt",
    description: "体验虚构姓名、邮箱、电话脱敏与共享账号风险。",
    text: marker + "岚桥虚构服务联系人：林澈，邮箱 linche@example.net，手机 13800138001。\n交付团队使用共享账号和明文密码。",
    redacted: marker + "岚桥虚构服务联系人：[PERSON_01]，邮箱 [EMAIL_01]，手机 [PHONE_01]。\n交付团队使用共享账号和明文密码。",
    points: 50, pii: 3,
    findings: [
      { category: "privacy", id: "PRIV-001", title: "检测到个人信息字段（虚构）", severity: "high", points: 18, evidence: "[PERSON_01]，邮箱 [EMAIL_01]，手机 [PHONE_01]", recommendation: "以最小化原则核验联系信息的必要性和访问范围。" },
      { category: "security", id: "SEC-004", title: "允许共享账号或明文凭据", severity: "critical", points: 32, evidence: "交付团队使用共享账号和明文密码。", recommendation: "改为独立身份、最小权限和凭据安全存储。" },
    ],
  },
  {
    id: "prepayment", title: "澄川交付协议：预付款", filename: "synthetic-prepayment.txt",
    description: "体验异常预付款和单方变更条款的预置风险。",
    text: marker + "澄川虚构设计向远汀虚构研究所交付演示材料。\n客户预付款90%，服务方可单方变更结算规则。",
    redacted: marker + "澄川虚构设计向远汀虚构研究所交付演示材料。\n客户预付款90%，服务方可单方变更结算规则。",
    points: 35, pii: 0,
    findings: [
      { category: "financial", id: "FIN-003", title: "异常预付款比例", severity: "high", points: 22, evidence: "客户预付款90%", recommendation: "改为按里程碑分期付款并绑定验收条件。" },
      { category: "legal", id: "LEGAL-006", title: "单方变更权", severity: "medium", points: 13, evidence: "服务方可单方变更结算规则。", recommendation: "要求实质变更经双方书面确认。" },
    ],
  },
  {
    id: "clean", title: "朔原标准附录：人工核验", filename: "synthetic-clean.txt",
    description: "体验零规则命中仍须人工决定，不自动批准。",
    text: marker + "朔原虚构工作室提供预置演示文稿。\n双方按里程碑验收并分期付款，变更须书面确认，责任上限由双方另行约定。",
    redacted: marker + "朔原虚构工作室提供预置演示文稿。\n双方按里程碑验收并分期付款，变更须书面确认，责任上限由双方另行约定。",
    points: 0, pii: 0, findings: [],
  },
];

export const DEMO_SAMPLES: readonly DemoSample[] = Object.freeze(scenarios.map(({ id, title, filename, description, text }) => Object.freeze({ id, title, filename, description, text })));
const INTAKE_MS = 2800;
const REPORT_MS = 1800;
const formats = ["json", "html"] as const;
const decisions = new Set<Decision>(["approved", "rejected", "changes_requested"]);

function copy<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function nowIso() { return new Date().toISOString(); }
function level(score: number) { return score >= 75 ? "critical" : score >= 50 ? "high" : score >= 25 ? "medium" : "low"; }
function abortIfNeeded(signal?: AbortSignal) { if (signal?.aborted) throw new DOMException("请求已取消。", "AbortError"); }
function fail(message: string, code: string, status = 409): never { throw new ApiError(message, status, code, null, false); }
function escapeHtml(value: unknown) { return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!); }
async function sha256(value: string): Promise<string> {
  if (!globalThis.crypto?.subtle) fail("当前浏览器不支持安全指纹计算，请使用现代浏览器打开 HTTPS 演示地址。", "demo_crypto_unavailable", 503);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
function section(text: string): DocumentSection[] { return [{ section_id: "demo-body", locator: "block:1", text }]; }

function findingsFor(sample: Scenario): Finding[] {
  return sample.findings.map((finding) => {
    const index = sample.redacted.indexOf(finding.evidence);
    const start = [...sample.redacted.slice(0, index)].length;
    return { rule_id: finding.id, category: finding.category, title: finding.title, severity: finding.severity, points: finding.points, evidence: finding.evidence, recommendation: finding.recommendation, section_id: "demo-body", locator: "block:1", start, end: start + [...finding.evidence].length, offset_basis: "unicode_code_points" };
  });
}

function assessedCase(sample: Scenario, id: string, hash: string): CaseDetail {
  const at = nowIso();
  const findings = findingsFor(sample);
  const dimensions: Record<string, number> = { privacy: 0, legal: 0, financial: 0, security: 0, policy: 0 };
  for (const finding of findings) dimensions[finding.category] = Math.min(100, dimensions[finding.category] + finding.points * 3);
  return {
    id, title: sample.title, document_name: sample.filename, document_type: "TXT", status: "pending_approval",
    risk_score: sample.points, risk_level: level(sample.points), owner: "demo-reviewer", submitted_at: at,
    due_at: new Date(Date.now() + 86400000).toISOString(), pii_count: sample.pii, decision: null,
    document_hash: hash, original_text: sample.text, redacted_text: sample.redacted, findings, dimensions,
    warnings: ["预置演示结果，不表示执行过真实文档解析、规则引擎、大模型或 Langflow。刷新页面后本次操作会清空。"],
    decision_reason: null, decided_by: null, decided_at: null, flow_run_id: null, ruleset_version: "browser-sandbox.1",
    audit_events: [{ id: 1, event_type: "case_scored", actor: "浏览器沙盒（模拟）", detail: "已载入预置虚构样本及演示评分，非真实工作流结果。", occurred_at: at }],
    current_document_version_id: `DV-${id}`, assessment_id: `AS-${id}`, row_version: 1,
    source_kind: "seed_demo", hash_kind: "synthetic_text",
    jobs: [{ job_id: `BJ-intake-${id}`, kind: "intake", state: "succeeded", phase: "completed", attempt: 1, retry_generation: 0, error_code: null, retryable: false, langflow_job_id: null, flow_id: null, flow_hash: null, created_at: at }],
    reports: [], parsed_sections: section(sample.text), redacted_sections: section(sample.redacted),
    source: { source_sha256: hash, hash_kind: "synthetic_text", bytes: new TextEncoder().encode(sample.text).byteLength, mime_type: "text/plain", source_kind: "seed_demo", legacy_flow_label: "浏览器沙盒模拟，不是 Langflow 运行", langflow_job_id: null, flow_id: null, flow_hash: null },
  };
}

function reportHtml(snapshot: Record<string, unknown>): string {
  const labels: Record<string, string> = { approved: "批准", rejected: "驳回", changes_requested: "要求修改" };
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>虚构演示决定报告</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:860px;margin:40px auto;padding:0 24px;color:#161616}h1{font-size:28px}pre{white-space:pre-wrap;overflow-wrap:anywhere}dl{display:grid;grid-template-columns:100px 1fr;gap:8px}dd{margin:0;overflow-wrap:anywhere}.notice{border:1px solid #8d8d8d;padding:12px}@media print{body{margin:12mm}h2{break-after:avoid}pre{break-inside:auto}}</style></head><body><p class="notice">${escapeHtml(DEMO_NOTICE)}</p><h1>虚构演示决定报告</h1><h2>${escapeHtml(snapshot.title)}</h2><dl><dt>案件</dt><dd>${escapeHtml(snapshot.case_id)}</dd><dt>文档版本</dt><dd>${escapeHtml(snapshot.document_version_id)}</dd><dt>演示规则分</dt><dd>${escapeHtml(snapshot.rule_score)}</dd><dt>人工决定</dt><dd>${escapeHtml(labels[String(snapshot.decision)] ?? snapshot.decision)}</dd><dt>演示身份</dt><dd>${escapeHtml(snapshot.reviewer)}</dd><dt>记录时间</dt><dd>${escapeHtml(snapshot.decided_at)}</dd></dl><h2>决定理由</h2><pre>${escapeHtml(snapshot.reason)}</pre><h2>脱敏后虚构正文</h2><pre>${escapeHtml(snapshot.redacted_text)}</pre><h2>预置演示发现</h2><pre>${escapeHtml(JSON.stringify(snapshot.findings, null, 2))}</pre><p>仅在当前浏览器内生成。此报告不能用作真实业务审查、真实 Langflow 执行或生产验收的证明。</p></body></html>`;
}

interface ReportRun { at: number; snapshot: Record<string, unknown>; hash: string; preparing?: Promise<void> }
interface IntakeRun { at: number; sample: Scenario; hash: string }

/** Creates a page-local sandbox. No timers, requests, or browser storage exist here. */
export function createDemoSandbox() {
  let epoch = 0;
  let counter = 0;
  let initialized: Promise<void> | null = null;
  let allowedFiles = new WeakMap<File, Scenario>();
  const cases = new Map<string, CaseDetail>();
  const intakes = new Map<string, IntakeRun>();
  const reportRuns = new Map<string, ReportRun>();
  const reportContents = new Map<string, { content: string; mime: string }>();
  const uploads = new Map<string, { signature: string; accepted: AcceptedTask }>();
  const savedDecisions = new Map<string, { signature: string }>();

  async function ready(signal?: AbortSignal) {
    abortIfNeeded(signal);
    if (!initialized) {
      const generation = epoch;
      initialized = Promise.all(scenarios.map(async (sample, index) => assessedCase(sample, `RC-BROWSER-${String(index + 1).padStart(3, "0")}`, await sha256(sample.text))))
        .then((items) => { if (generation === epoch) items.forEach((item) => cases.set(item.id, item)); });
    }
    const generation = epoch;
    await initialized;
    abortIfNeeded(signal);
    if (generation !== epoch) throw new DOMException("演示已重置。", "AbortError");
  }

  function requireCase(id: string) {
    const detail = cases.get(id);
    if (!detail) fail("该演示案件不存在，或已在刷新/重置时清空。", "case_not_found", 404);
    return detail;
  }

  async function advance(signal?: AbortSignal) {
    await ready(signal);
    const generation = epoch;
    for (const [id, run] of intakes) {
      const detail = requireCase(id);
      const elapsed = Date.now() - run.at;
      const job = detail.jobs[0];
      if (elapsed >= INTAKE_MS) {
        const assessed = assessedCase(run.sample, id, run.hash);
        assessed.submitted_at = detail.submitted_at;
        assessed.row_version = detail.row_version + 1;
        assessed.audit_events = [...detail.audit_events, { id: 2, event_type: "intake_succeeded", actor: "浏览器沙盒（模拟）", detail: "预置解析、脱敏和规则评分展示完成；未调用真实服务。", occurred_at: nowIso() }];
        cases.set(id, assessed);
        intakes.delete(id);
      } else if (elapsed >= 400) {
        detail.status = "processing";
        job.state = "running";
        job.phase = elapsed < 1100 ? "parsing" : elapsed < 1900 ? "redacting" : "scoring";
        job.attempt = 1;
      }
    }
    for (const [id, run] of reportRuns) {
      const detail = requireCase(id);
      const job = detail.jobs.find((item) => item.kind === "report")!;
      if (Date.now() - run.at < REPORT_MS) {
        if (Date.now() - run.at >= 350) { job.state = "running"; job.phase = "generating"; detail.reports.forEach((item) => { item.state = "processing"; }); }
        continue;
      }
      if (!run.preparing) {
        run.preparing = (async () => {
          const contents = { json: JSON.stringify({ ...run.snapshot, snapshot_hash: run.hash }, null, 2), html: reportHtml(run.snapshot) };
          const artifacts = await Promise.all(formats.map(async (format): Promise<ReportArtifact> => {
            const content = contents[format];
            return { report_id: `BR-${id}-${format}`, format, state: "ready", snapshot_hash: run.hash, sha256: await sha256(content), bytes: new TextEncoder().encode(content).byteLength, created_at: nowIso() };
          }));
          if (generation !== epoch || cases.get(id) !== detail || reportRuns.get(id) !== run) return;
          for (const format of formats) reportContents.set(`BR-${id}-${format}`, { content: contents[format], mime: format === "json" ? "application/json;charset=utf-8" : "text/html;charset=utf-8" });
          detail.reports = artifacts;
          job.state = "succeeded"; job.phase = "completed";
          detail.audit_events.push({ id: detail.audit_events.length + 1, event_type: "report_ready", actor: "浏览器沙盒（模拟）", detail: "JSON/HTML 演示报告已在当前页面内生成；PDF 可通过浏览器打印另存。", occurred_at: nowIso() });
          reportRuns.delete(id);
        })();
      }
      await run.preparing;
      if (generation !== epoch) throw new DOMException("演示已重置。", "AbortError");
    }
    abortIfNeeded(signal);
  }

  function createDemoFile(sampleId: string): File {
    const sample = scenarios.find((item) => item.id === sampleId);
    if (!sample) fail("请选择页面提供的预置虚构样本。", "demo_sample_unknown", 422);
    const file = new File([sample.text], sample.filename, { type: "text/plain" });
    allowedFiles.set(file, sample);
    return file;
  }

  const api = {
    async summary(signal?: AbortSignal): Promise<DashboardSummary> {
      await advance(signal);
      const all = [...cases.values()];
      const scored = all.filter((item) => item.assessment_id !== null && item.risk_score !== null);
      const risk_distribution = { low: 0, medium: 0, high: 0, critical: 0 };
      const category_distribution: Record<string, number> = { privacy: 0, legal: 0, financial: 0, security: 0, policy: 0 };
      for (const item of scored) {
        risk_distribution[item.risk_level!] += 1;
        item.findings.forEach((finding) => { category_distribution[finding.category] += 1; });
      }
      return { total_cases: all.length, pending_approval: all.filter((item) => item.status === "pending_approval").length, high_risk: scored.filter((item) => item.risk_level === "high" || item.risk_level === "critical").length, completed: all.filter((item) => item.decision !== null).length, average_score: scored.length ? Math.round(scored.reduce((sum, item) => sum + item.risk_score!, 0) / scored.length * 10) / 10 : null, scored_cases: scored.length, risk_distribution, category_distribution, system_status: { api: "unknown", database: "unknown", worker: "unknown", langflow: "unknown" }, ruleset_version: "browser-sandbox.1" };
    },
    async cases(signal?: AbortSignal): Promise<CaseSummary[]> {
      await advance(signal);
      return copy([...cases.values()].reverse().map((item) => ({ id: item.id, title: item.title, document_name: item.document_name, document_type: item.document_type, status: item.status, risk_score: item.risk_score, risk_level: item.risk_level, owner: item.owner, submitted_at: item.submitted_at, due_at: item.due_at, pii_count: item.pii_count, decision: item.decision, source_kind: item.source_kind, current_document_version_id: item.current_document_version_id, row_version: item.row_version })));
    },
    async case(caseId: string, signal?: AbortSignal): Promise<CaseDetail> { await advance(signal); return copy(requireCase(caseId)); },
    async systemStatus(signal?: AbortSignal): Promise<SystemStatus> {
      abortIfNeeded(signal);
      const checked_at = nowIso();
      return { checked_at, services: Object.fromEntries(["api", "database", "worker", "langflow"].map((key) => [key, { state: "unknown" as const, checked_at, detail: "前端沙盒，未连接真实服务" }])) };
    },
    async upload(file: File, title: string, key: string, signal?: AbortSignal): Promise<AcceptedTask> {
      abortIfNeeded(signal);
      const generation = epoch;
      const sample = allowedFiles.get(file);
      if (!sample) fail("在线演示只接受页面提供的预置虚构样本，不读取或上传设备上的文件。", "demo_files_not_allowed", 422);
      if (title.trim() !== sample.title || !key.trim()) fail("请使用所选预置样本的标题。", "demo_sample_invalid", 422);
      await advance(signal);
      if (generation !== epoch) throw new DOMException("演示已重置。", "AbortError");
      const signature = `${sample.id}:${title.trim()}`;
      const prior = uploads.get(key);
      if (prior) {
        if (prior.signature !== signature) fail("该请求编号已用于另一预置样本。", "idempotency_conflict");
        return copy(prior.accepted);
      }
      if (cases.size >= 28) fail("本页演示案件已达到上限，请重置演示后继续。", "demo_capacity_reached", 429);
      const hash = await sha256(sample.text);
      abortIfNeeded(signal);
      if (generation !== epoch) throw new DOMException("演示已重置。", "AbortError");
      const concurrent = uploads.get(key);
      if (concurrent) {
        if (concurrent.signature !== signature) fail("该请求编号已用于另一预置样本。", "idempotency_conflict");
        return copy(concurrent.accepted);
      }
      if (cases.size >= 28) fail("本页演示案件已达到上限，请重置演示后继续。", "demo_capacity_reached", 429);
      const id = `RC-BROWSER-NEW-${String(++counter).padStart(3, "0")}`;
      const detail = assessedCase(sample, id, hash);
      detail.status = "received"; detail.risk_score = null; detail.risk_level = null; detail.assessment_id = null;
      detail.pii_count = 0; detail.findings = []; detail.dimensions = {}; detail.original_text = ""; detail.redacted_text = ""; detail.parsed_sections = []; detail.redacted_sections = [];
      detail.jobs[0].state = "queued"; detail.jobs[0].phase = "queued"; detail.jobs[0].attempt = 0;
      detail.audit_events = [{ id: 1, event_type: "case_received", actor: "浏览器沙盒（模拟）", detail: "已选择预置虚构样本，仅在当前页面内展示处理过程。", occurred_at: nowIso() }];
      cases.set(id, detail); intakes.set(id, { at: Date.now(), sample, hash });
      const accepted: AcceptedTask = { case_id: id, document_version_id: detail.current_document_version_id!, job_id: detail.jobs[0].job_id, status: "received", request_id: `browser-request-${counter}` };
      uploads.set(key, { signature, accepted });
      return copy(accepted);
    },
    async decide(input: CaseDetail, decision: Decision, reason: string, reviewer: string, key: string, signal?: AbortSignal): Promise<CaseDetail> {
      const generation = epoch;
      await advance(signal);
      if (generation !== epoch) throw new DOMException("演示已重置。", "AbortError");
      const trimmed = reason.trim();
      if (!decisions.has(decision) || [...trimmed].length < 8 || [...trimmed].length > 1000 || !reviewer.trim() || reviewer.length > 80 || !key.trim()) fail("请选择决定，使用演示身份，并填写 8-1000 个字符的虚构理由。", "validation_error", 422);
      const signature = JSON.stringify([decision, trimmed, reviewer.trim(), input.current_document_version_id, input.assessment_id, input.row_version]);
      const cacheKey = `${input.id}:${key}`;
      const previous = savedDecisions.get(cacheKey);
      if (previous) {
        if (previous.signature !== signature) fail("同一请求编号不能用于不同决定。", "idempotency_conflict");
        return copy(requireCase(input.id));
      }
      const detail = requireCase(input.id);
      const validate = () => { if (detail.decision || detail.status !== "pending_approval" || !detail.assessment_id || detail.current_document_version_id !== input.current_document_version_id || detail.assessment_id !== input.assessment_id || detail.row_version !== input.row_version) fail("该演示版本已有决定或已变化，请刷新案件。", "decision_conflict"); };
      validate();
      const at = nowIso();
      const snapshot: Record<string, unknown> = { classification: DEMO_NOTICE, mode: "browser_sandbox_simulation", case_id: detail.id, title: detail.title, document_version_id: detail.current_document_version_id, assessment_id: detail.assessment_id, source_kind: "seed_demo", hash_kind: "synthetic_text", source_sha256: detail.document_hash, rule_score: detail.risk_score, risk_level: detail.risk_level, ruleset_version: detail.ruleset_version, findings: copy(detail.findings), redacted_text: detail.redacted_text, decision, reason: trimmed, reviewer: reviewer.trim(), decided_at: at, real_langflow_run_id: null };
      const hash = await sha256(JSON.stringify(snapshot));
      abortIfNeeded(signal);
      if (generation !== epoch || cases.get(input.id) !== detail) throw new DOMException("演示已重置。", "AbortError");
      const concurrent = savedDecisions.get(cacheKey);
      if (concurrent) {
        if (concurrent.signature !== signature) fail("同一请求编号不能用于不同决定。", "idempotency_conflict");
        return copy(detail);
      }
      validate();
      detail.decision = decision; detail.status = decision; detail.decision_reason = trimmed; detail.decided_by = reviewer.trim(); detail.decided_at = at; detail.decision_id = `BD-${detail.id}`; detail.row_version += 1;
      detail.audit_events.push({ id: detail.audit_events.length + 1, event_type: "decision_recorded", actor: "demo-reviewer（本页模拟）", detail: `已记录演示决定 ${decision}；本页内保存，不会写入服务器。理由：${trimmed}`, occurred_at: at });
      detail.jobs.unshift({ job_id: `BJ-report-${detail.id}`, kind: "report", state: "queued", phase: "queued", attempt: 1, retry_generation: 0, error_code: null, retryable: false, langflow_job_id: null, flow_id: null, flow_hash: null, created_at: at });
      detail.reports = formats.map((format) => ({ report_id: `BR-${detail.id}-${format}`, format, state: "queued", snapshot_hash: hash, sha256: null, bytes: null, created_at: null }));
      reportRuns.set(detail.id, { at: Date.now(), snapshot, hash });
      savedDecisions.set(cacheKey, { signature });
      return copy(detail);
    },
    async retry(_detail: CaseDetail, _jobId: string, _key: string, signal?: AbortSignal): Promise<WorkflowJob> { abortIfNeeded(signal); fail("此沙盒不执行真实任务重试，请重置演示或选择新的预置样本。", "demo_retry_not_available"); },
    async retryReports(_caseId: string, _snapshotHash: string, _formats: ReportFormat[], _key: string, signal?: AbortSignal): Promise<WorkflowJob> { abortIfNeeded(signal); fail("本页仅生成 JSON/HTML 演示报告；PDF 请使用浏览器打印另存。", "demo_report_retry_not_available"); },
    reportUrl: (_caseId: string, _format: ReportFormat, _reportId?: string) => "#demo-report",
    async downloadReport(caseId: string, format: ReportFormat, reportId: string, signal?: AbortSignal): Promise<Blob> {
      await advance(signal);
      const detail = requireCase(caseId);
      if (!detail.decision || !decisions.has(detail.status as Decision)) fail("须先记录该版本的人工演示决定，才能下载报告。", "report_not_ready");
      const artifact = detail.reports.find((item) => item.format === format && item.report_id === reportId && item.state === "ready");
      const stored = artifact && reportContents.get(reportId);
      if (!stored) fail("该格式尚未就绪。PDF 请从 HTML 演示报告使用浏览器打印另存。", "report_not_ready");
      return new Blob([stored.content], { type: stored.mime });
    },
  };

  function reset() {
    epoch += 1; counter = 0; initialized = null; allowedFiles = new WeakMap();
    cases.clear(); intakes.clear(); reportRuns.clear(); reportContents.clear(); uploads.clear(); savedDecisions.clear();
  }
  return { api, createDemoFile, reset };
}

const sandbox = createDemoSandbox();
export const demoApi = sandbox.api;
export const createDemoFile = sandbox.createDemoFile;
export const resetDemo = sandbox.reset;
