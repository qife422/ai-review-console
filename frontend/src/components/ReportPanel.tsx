import { Download, Renew } from "@carbon/icons-react";
import { Button, InlineNotification, Tag, Tile } from "@carbon/react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { isPublicDemo } from "../demoMode";
import type { CaseDetail, ReportArtifact, ReportFormat } from "../types";
import { activeJobStates, decidedStates, errorMessage, formatDate } from "../workflow";

const formats: ReportFormat[] = isPublicDemo ? ["json", "html"] : ["json", "html", "pdf"];
const stateLabels: Record<string, string> = { queued: "等待生成", processing: "生成中", ready: "可下载", failed: "生成失败", missing: "尚未生成", previous_version: "历史版本" };

export function ReportPanel({ detail, onRefresh }: { detail: CaseDetail; onRefresh: () => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState<ReportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorTitle, setErrorTitle] = useState("报告重试未登记");
  const key = useRef(crypto.randomUUID());
  const keyPayload = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const blobUrls = useRef(new Set<string>());
  const printFrames = useRef(new Set<HTMLIFrameElement>());
  useEffect(() => () => { controller.current?.abort(); blobUrls.current.forEach((url) => URL.revokeObjectURL(url)); printFrames.current.forEach((frame) => frame.remove()); }, []);
  const decided = !!detail.decision && decidedStates.has(detail.status);
  const reports = detail.reports ?? [];
  const retryable = reports.filter((item) => ["failed", "missing"].includes(item.state));
  const activeJob = (detail.jobs ?? []).find((job) => job.kind === "report" && activeJobStates.has(job.state));
  const latestReportJob = (detail.jobs ?? []).find((job) => job.kind === "report");
  const retryLimitReached = (latestReportJob?.retry_generation ?? 0) >= 3;
  const readyCount = reports.filter((item) => item.state === "ready").length;
  const partial = readyCount > 0 && readyCount < formats.length;

  async function retry() {
    if (!retryable.length || saving || activeJob || !decided) return;
    const snapshot = retryable[0].snapshot_hash;
    if (!snapshot || retryable.some((item) => item.snapshot_hash !== snapshot)) return;
    const signature = `${snapshot}:${retryable.map((item) => item.format).sort().join(",")}`;
    if (keyPayload.current !== signature) { key.current = crypto.randomUUID(); keyPayload.current = signature; }
    setSaving(true);
    setError(null);
    setErrorTitle("报告重试未登记");
    controller.current = new AbortController();
    try {
      await api.retryReports(detail.id, snapshot, retryable.map((item) => item.format), key.current, controller.current.signal);
      await onRefresh();
      key.current = crypto.randomUUID();
    } catch (requestError) {
      if (!controller.current.signal.aborted) setError(errorMessage(requestError));
    } finally {
      if (!controller.current.signal.aborted) setSaving(false);
    }
  }

  async function download(report: ReportArtifact) {
    if (!decided || report.state !== "ready" || downloading || saving) return;
    setDownloading(report.format);
    setError(null);
    setErrorTitle("报告下载失败");
    controller.current = new AbortController();
    try {
      const blob = await api.downloadReport(detail.id, report.format, report.report_id, controller.current.signal);
      if (controller.current.signal.aborted) return;
      const url = URL.createObjectURL(blob);
      blobUrls.current.add(url);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${detail.id}-report.${report.format}`;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => { URL.revokeObjectURL(url); blobUrls.current.delete(url); }, 1000);
    } catch (requestError) {
      if (!controller.current.signal.aborted) setError(errorMessage(requestError));
    } finally {
      if (!controller.current.signal.aborted) setDownloading(null);
    }
  }

  async function printDemoReport() {
    const report = reports.find((item) => item.format === "html" && item.state === "ready");
    if (!isPublicDemo || !decided || !report || saving || downloading) return;
    setSaving(true);
    setError(null);
    setErrorTitle("无法打开打印预览");
    try {
      const blob = await api.downloadReport(detail.id, "html", report.report_id);
      const url = URL.createObjectURL(blob);
      blobUrls.current.add(url);
      const frame = document.createElement("iframe");
      printFrames.current.add(frame);
      frame.title = "虚构报告打印预览";
      frame.style.cssText = "position:fixed;width:1px;height:1px;left:-10000px;top:0;border:0";
      const cleanup = () => { frame.remove(); printFrames.current.delete(frame); URL.revokeObjectURL(url); blobUrls.current.delete(url); };
      frame.onload = () => {
        try { frame.contentWindow?.addEventListener("afterprint", cleanup, { once: true }); frame.contentWindow?.focus(); frame.contentWindow?.print(); }
        catch { setError("浏览器未能打开打印预览，请下载 HTML 后使用浏览器打印。") ; cleanup(); }
      };
      frame.src = url;
      document.body.append(frame);
      setTimeout(cleanup, 120_000);
    } catch (requestError) { setError(errorMessage(requestError)); }
    finally { setSaving(false); }
  }

  return (
    <Tile className="report-panel">
      <div className="workflow-panel-heading"><h2>报告生成</h2><Tag type={readyCount === formats.length ? "green" : !decided ? "gray" : "blue"}>{readyCount === formats.length ? isPublicDemo ? "JSON / HTML 可下载" : "三种格式均可下载" : partial ? "部分格式可用" : decided ? "决定已保存" : "等待人工决定"}</Tag></div>
      <p className="workflow-copy">{isPublicDemo ? "人工决定后，仅在浏览器内生成本次虚构报告；可下载 JSON、HTML，或通过浏览器打印另存 PDF。不是后台 Decision Flow 产物。" : !decided ? "人工决定记录后，系统才会生成该版本的决定报告。" : detail.decision === "changes_requested" ? "本次修订意见已保存，报告记录该版本需要修改的事项。" : "人工决定已保存。报告通过 Decision Flow 独立生成，失败不会改变决定。"}</p>
      {partial && <p className="field-helper" role="status">已生成格式可单独下载；未成功的格式仍需完成处理。</p>}
      <div className="report-format-list">{formats.map((format) => {
        const report = reports.find((item) => item.format === format);
        const state = report?.state ?? "missing";
        const canDownload = decided && state === "ready" && !!report?.report_id;
        return <div className="report-format" key={format}><div><strong>{format.toUpperCase()}</strong><Tag type={state === "ready" ? "green" : state === "failed" ? "red" : "gray"}>{!decided ? "未开放" : stateLabels[state] ?? "状态未知"}</Tag></div><div className="report-format-meta">{state === "ready" ? <span>{report?.bytes !== null && report?.bytes !== undefined ? `${(report.bytes / 1024).toFixed(1)} KiB` : "大小未记录"}，{formatDate(report?.created_at)}</span> : <span>{report?.error_code ? `错误：${report.error_code}` : activeJob ? "后台任务处理中" : "尚无可下载产物"}</span>}</div>{canDownload ? <Button size="sm" kind="tertiary" disabled={!!downloading || saving} renderIcon={Download} onClick={() => download(report)}>{downloading === format ? "正在下载" : `下载 ${format.toUpperCase()}`}</Button> : <Button size="sm" kind="tertiary" disabled>下载 {format.toUpperCase()}</Button>}{state === "ready" && report?.sha256 && <details className="artifact-fingerprint"><summary>文件指纹</summary><code>SHA-256: {report.sha256}</code></details>}</div>;
      })}</div>
      {isPublicDemo && <Button size="sm" kind="tertiary" disabled={!decided || !reports.some((item) => item.format === "html" && item.state === "ready") || saving || !!downloading} onClick={() => void printDemoReport()}>打印 / 另存 PDF</Button>}
      {decided && retryable.length > 0 && <Button size="sm" kind="tertiary" renderIcon={Renew} disabled={saving || !!downloading || !!activeJob || retryLimitReached || !retryable[0].snapshot_hash} onClick={retry}>{saving ? "正在登记重试" : activeJob ? "后台正在重试" : retryLimitReached ? "已达重试上限" : "重试未完成格式"}</Button>}
      {decided && reports.length === 0 && <p className="field-helper">尚未登记该决定快照的报告，请重新加载状态。</p>}
      {activeJob?.state === "retry_wait" && <p className="field-helper">报告任务等待自动重试；已就绪格式会保留。</p>}
      {error && <InlineNotification kind="error" lowContrast hideCloseButton title={errorTitle} subtitle={error} />}
    </Tile>
  );
}
