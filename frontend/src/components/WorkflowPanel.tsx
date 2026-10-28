import { Renew } from "@carbon/icons-react";
import { Button, InlineNotification, Tag, Tile } from "@carbon/react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { isPublicDemo } from "../demoMode";
import type { CaseDetail } from "../types";
import { errorMessage, jobError, phaseLabels } from "../workflow";

export function WorkflowPanel({ detail, onRefresh }: { detail: CaseDetail; onRefresh: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef(crypto.randomUUID());
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const job = (detail.jobs ?? []).find((item) => item.kind === "intake");
  const state = job?.state;
  const labels = { queued: "等待执行", running: "处理中", retry_wait: "等待自动重试", succeeded: "已保存结果", failed: "处理失败" };
  const complete = detail.risk_score !== null && !!detail.assessment_id;

  async function retry() {
    if (!job || saving) return;
    setSaving(true);
    setError(null);
    controller.current = new AbortController();
    try {
      await api.retry(detail, job.job_id, key.current, controller.current.signal);
      await onRefresh();
      key.current = crypto.randomUUID();
    } catch (requestError) {
      if (!controller.current.signal.aborted) setError(errorMessage(requestError));
    } finally {
      if (!controller.current.signal.aborted) setSaving(false);
    }
  }

  return (
    <Tile className="workflow-panel">
      <div className="workflow-panel-heading"><h2>文档处理</h2><Tag type={state === "failed" ? "red" : complete ? "green" : "blue"}>{state ? labels[state] : complete ? "审查结果已保存" : "状态待确认"}</Tag></div>
      {isPublicDemo ? <p className="workflow-copy">浏览器内模拟解析、脱敏与评分进度；预设结果仅供体验，不是实时规则执行或真实 Intake Flow。</p> : detail.source_kind === "seed_demo" ? <p className="workflow-copy">历史虚构种子案例，结果用于演示；不表示已执行真实 Intake Flow。</p> :
        <p className="workflow-copy">{complete ? "解析、脱敏和规则评估已持久化，等待或保留人工决定。" : "后台执行解析、脱敏与规则评估，当前没有完整风险评分。"}</p>}
      {job && <div className="job-progress" role="status"><span>{phaseLabels[job.phase] ?? (state ? labels[state] : "工作流处理")}</span><small>{job.attempt ? `第 ${job.attempt} 次执行` : "尚未开始执行"}{state === "retry_wait" ? "，系统将按策略自动重试" : ""}</small></div>}
      {state === "failed" && job && <InlineNotification kind="error" lowContrast hideCloseButton title="文档处理未完成" subtitle={jobError(job)} />}
      {detail.status === "failed" && !detail.decision && job?.state === "failed" && job.retryable && <Button size="sm" kind="tertiary" disabled={saving} renderIcon={Renew} onClick={retry}>{saving ? "正在登记重试" : "重试文档处理"}</Button>}
      {detail.status === "failed" && job && !job.retryable && <p className="field-helper">该错误不能直接重试。请检查文档内容或运行配置后提交新的虚构文档。</p>}
      {error && <InlineNotification kind="error" lowContrast hideCloseButton title="无法登记重试" subtitle={error} />}
      {job && <details className="execution-details"><summary>任务运行记录</summary><dl><dt>任务编号</dt><dd>{job.job_id}</dd><dt>上游运行编号</dt><dd>{job.langflow_job_id ?? "尚未取得真实运行编号"}</dd>{job.error_code && <><dt>错误代码</dt><dd>{job.error_code}</dd></>}</dl></details>}
    </Tile>
  );
}
