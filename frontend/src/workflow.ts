import { ApiError } from "./api";
import type { CaseDetail, CaseSummary, WorkflowJob } from "./types";

export const activeJobStates = new Set(["queued", "running", "retry_wait"]);
export const decidedStates = new Set(["approved", "rejected", "changes_requested"]);

export const phaseLabels: Record<string, string> = {
  queued: "等待执行", starting: "准备工作流", parsing: "解析文档", parsed: "解析完成",
  redacting: "脱敏处理", redacted: "脱敏完成", scoring: "规则评分", scored: "评分完成",
  submitting: "保存审查结果", intake: "文档处理", report: "报告生成", exporting: "生成报告",
  generating: "生成报告", registering: "登记报告", succeeded: "处理完成", completed: "处理完成",
  pending_approval: "待人工审批", failed: "处理失败", running: "工作流执行中",
  retry_wait: "等待自动重试", callback: "保存审查结果",
  starting_flow: "准备工作流", running_flow: "工作流执行中", polling: "等待工作流结果",
  failure_pending: "协调处理失败状态", result_persisted: "结果已保存",
};

const errorLabels: Record<string, string> = {
  queue_capacity_exceeded: "待处理任务已达到容量限制，请稍后提交。",
  idempotency_conflict: "这次请求的内容已改变，请重新选择文件或重新打开决定窗口。",
  requires_ocr: "文档包含无法提取的扫描内容。当前版本暂不支持 OCR，请上传可提取文本的文档。",
  unsupported_content: "文档包含当前解析器不支持的内容，请使用支持的正文结构。",
  unsupported_document_type: "仅支持 PDF、DOCX、TXT 和 MD 文档。",
  invalid_document: "文档结构无效或与文件扩展名不一致，请检查文件。",
  invalid_utf8: "TXT 和 MD 文档需要使用有效的 UTF-8 编码。",
  synthetic_marker_missing: "正文必须包含 SYNTHETIC DEMO DOCUMENT 虚构标识。",
  missing_synthetic_marker: "正文必须包含 SYNTHETIC DEMO DOCUMENT 虚构标识。",
  empty_document: "文档没有可提取的正文，请检查文件内容。",
  encrypted_pdf: "当前版本不支持加密 PDF，请使用未加密的虚构文档。",
  stale_version: "案件版本已经更新，请查看最新结果后再作决定。",
  decision_conflict: "该文档版本已有人工决定，已刷新最新结果。",
  langflow_unavailable: "Langflow 暂时不可用，任务会按重试策略处理。",
  langflow_timeout: "工作流执行超时，请查看任务状态和重试结果。",
  retry_limit_exceeded: "已达到手动重试限制，请根据任务错误检查运行环境。",
  retry_limit_reached: "已达到手动重试限制，请根据任务错误检查运行环境。",
  unsupported_type: "仅支持 PDF、DOCX、TXT 和 MD 文档。",
  type_mismatch: "文件结构与扩展名不一致，请检查文件格式。",
  empty_text: "文档没有可提取的正文，请使用含可提取文本的虚构文档。",
  invalid_encoding: "TXT 和 MD 文档需要使用有效的 UTF-8 编码。",
  file_too_large: "单个文档不能超过 10 MiB。",
  text_too_large: "解析正文超过 1 MiB，请缩小文档内容。",
  page_limit_exceeded: "PDF 不能超过 200 页。",
  invalid_pdf: "PDF 结构损坏或无法解析，请检查文件。",
  invalid_docx: "DOCX 结构损坏或不符合支持范围，请检查文件。",
  langflow_auth_failed: "Langflow 身份验证失败，请检查服务端配置后重试。",
  langflow_auth_unconfigured: "尚未配置 Langflow 服务端身份，请完成配置后重试。",
  langflow_not_found: "绑定的工作流尚未找到，请检查已发布的 Flow 配置。",
  langflow_rate_limited: "Langflow 暂时限制请求，系统会按重试策略处理。",
  workflow_timeout: "工作流超过本次执行时限，请查看重试状态。",
  result_not_persisted: "工作流结束但业务结果没有成功保存，请查看任务并重试。",
  callback_unavailable: "审查结果暂时无法回传，后台会协调或重试。",
  callback_timeout: "结果登记请求超时，后台会核对是否已保存。",
  report_job_active: "报告生成任务正在运行，请等待当前任务完成。",
  report_retry_not_allowed: "仅允许重试失败或缺失的格式，已就绪报告不会重写。",
  retry_not_allowed: "当前案件不符合重试条件，请刷新状态。",
  report_file_missing: "登记的报告文件不可读取，请核对运行产物。",
  report_integrity_invalid: "报告字节与登记指纹不一致，下载已停止。请核对运行产物。",
  report_not_ready: "该格式报告尚未就绪，请刷新处理状态。",
};

export function errorMessage(error: unknown, fallback = "请求失败，请稍后重试。"): string {
  if (error instanceof ApiError) return errorLabels[error.code] ?? error.message;
  return error instanceof Error ? error.message : fallback;
}

export function jobError(job: WorkflowJob): string {
  return (job.error_code && errorLabels[job.error_code]) || job.error_detail || "处理未完成，请检查任务状态。";
}

export function hasActiveWork(detail: CaseDetail | null): boolean {
  if (!detail) return false;
  return ["received", "processing"].includes(detail.status) ||
    (detail.jobs ?? []).some((job) => activeJobStates.has(job.state)) ||
    (detail.reports ?? []).some((report) => ["queued", "processing"].includes(report.state));
}

export function hasProcessingCases(cases: CaseSummary[]): boolean {
  return cases.some((item) => ["received", "processing"].includes(item.status));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "尚未记录";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "时间未知" : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
