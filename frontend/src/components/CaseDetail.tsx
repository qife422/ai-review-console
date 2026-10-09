import { ArrowLeft, Checkmark, Renew, WarningAlt } from "@carbon/icons-react";
import { Button, CodeSnippet, InlineNotification, Modal, SkeletonText, Tab, TabList, TabPanel, TabPanels, Tabs, TextArea, Tile } from "@carbon/react";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { CaseDetail as CaseDetailType, Decision, DocumentSection, Finding } from "../types";
import { errorMessage, formatDate } from "../workflow";
import { ReportPanel } from "./ReportPanel";
import { RiskTag, StatusTag } from "./StatusTag";
import { WorkflowPanel } from "./WorkflowPanel";

interface CaseDetailProps {
  detail: CaseDetailType | null;
  loading: boolean;
  error: string | null;
  notice?: string | null;
  onDismissNotice: () => void;
  onBack: () => void;
  onReload: () => void;
  onRefresh: () => Promise<void>;
  onDecided: (detail: CaseDetailType) => void;
}

const decisionLabels: Record<Decision, string> = { approved: "批准", rejected: "驳回", changes_requested: "要求修改" };
const dimensionLabels: Record<string, string> = { privacy: "隐私", legal: "法律条款", financial: "财务", security: "信息安全", policy: "内部政策" };
const eventLabels: Record<string, string> = { case_scored: "规则评分完成", decision_recorded: "人工决定已记录", case_received: "虚构文档已接受", intake_succeeded: "审查结果已保存", intake_failed: "文档处理失败", report_ready: "报告已登记", report_failed: "报告生成失败", retry_requested: "重试已登记", legacy_state_migrated: "历史状态已迁移" };

function sectionElementId(sectionId: string) { return `evidence-section-${encodeURIComponent(sectionId)}`; }

function DocumentSections({ sections, fallback, redacted, highlighted }: { sections: DocumentSection[]; fallback: string; redacted: boolean; highlighted: string | null }) {
  if (!sections.length) return <pre>{fallback || "尚无可展示的正文。"}</pre>;
  return <div className="document-sections">{sections.map((section) => <section key={section.section_id} id={redacted ? sectionElementId(section.section_id) : undefined} tabIndex={redacted ? -1 : undefined} className={highlighted === section.section_id && redacted ? "document-section highlighted-section" : "document-section"}><small>{section.locator}</small><pre>{section.text}</pre></section>)}</div>;
}

export function CaseDetail({ detail, loading, error, notice, onDismissNotice, onBack, onReload, onRefresh, onDecided }: CaseDetailProps) {
  const [dialog, setDialog] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [selectedTab, setSelectedTab] = useState(0);
  const [highlightedSection, setHighlightedSection] = useState<string | null>(null);
  const decisionKey = useRef(crypto.randomUUID());
  const decisionLauncher = useRef<HTMLButtonElement | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (selectedTab !== 1 || !highlightedSection) return;
    const frame = requestAnimationFrame(() => {
      const element = document.getElementById(sectionElementId(highlightedSection));
      element?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      element?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [selectedTab, highlightedSection]);

  if (loading) return <div className="detail-loading" aria-label="正在加载案件"><SkeletonText heading /><SkeletonText paragraph lineCount={8} /></div>;
  if (!detail) return <div className="error-state"><InlineNotification kind="error" title="无法加载案件" subtitle={error ?? "案件不存在"} /><Button size="sm" onClick={onReload}>重试</Button><Button kind="ghost" size="sm" onClick={onBack}>返回审查队列</Button></div>;

  const hasAssessment = detail.risk_score !== null && !!detail.assessment_id;
  const canDecide = detail.status === "pending_approval" && !detail.decision && hasAssessment && !!detail.current_document_version_id;
  const parsedSections = detail.parsed_sections ?? [];
  const redactedSections = detail.redacted_sections ?? [];
  const liveRunId = detail.source?.langflow_job_id || (detail.jobs ?? []).find((job) => job.kind === "intake" && job.langflow_job_id)?.langflow_job_id || (detail.source_kind !== "seed_demo" ? detail.flow_run_id : null);
  const reasonLength = [...reason.trim()].length;

  function selectDecision(decision: Decision) {
    setDialog(decision);
    setSaveError(null);
    decisionKey.current = crypto.randomUUID();
  }

  async function submitDecision() {
    if (!dialog || reasonLength < 8 || reasonLength > 1000 || saving || !canDecide) return;
    setSaving(true);
    setSaveError(null);
    controller.current = new AbortController();
    try {
      const updated = await api.decide(detail!, dialog, reason, "demo-reviewer", decisionKey.current, controller.current.signal);
      onDecided(updated);
      setDialog(null);
      setReason("");
    } catch (requestError) {
      if (controller.current.signal.aborted) return;
      if (requestError instanceof ApiError && requestError.status === 409) {
        setDialog(null);
        setConflict("本次决定未提交。案件版本或已有决定发生变化，已重新读取最新结果，请核验后继续。");
        await onRefresh();
      } else setSaveError(errorMessage(requestError, "保存决定失败"));
    } finally {
      if (!controller.current.signal.aborted) setSaving(false);
    }
  }

  function jumpToEvidence(finding: Finding) {
    const section = redactedSections.find((item) => item.section_id === finding.section_id || (finding.locator && item.locator === finding.locator));
    if (!section) return;
    setHighlightedSection(section.section_id);
    setSelectedTab(1);
  }

  return (
    <>
      <Button kind="ghost" size="sm" renderIcon={ArrowLeft} onClick={onBack} className="back-button">返回审查队列</Button>
      {notice && <InlineNotification className="detail-notice" lowContrast kind="success" title="文档已提交" subtitle={notice} onClose={onDismissNotice} />}
      {error && <InlineNotification className="detail-notice" lowContrast hideCloseButton kind="error" title="最新状态暂未取得" subtitle={error} />}
      {conflict && <InlineNotification className="detail-notice" lowContrast kind="warning" title="决定冲突" subtitle={conflict} onClose={() => setConflict(null)} />}
      <section className="detail-header">
        <div><span>{detail.id}</span><h1 tabIndex={-1}>{detail.title}</h1><div className="tag-row"><StatusTag status={detail.status} /><RiskTag level={detail.risk_level} /></div></div>
        <div className="decision-actions"><Button kind="tertiary" onClick={onReload}>刷新状态</Button><Button ref={decisionLauncher} disabled={!canDecide} renderIcon={Checkmark} onClick={() => selectDecision("approved")}>记录决定</Button></div>
      </section>

      <div className="source-notice"><strong>{detail.source_kind === "seed_demo" ? "历史种子演示" : detail.source_kind === "uploaded_demo" ? "新增虚构文档" : "来源未标识"}</strong><span>{detail.source_kind === "seed_demo" ? "示例字段不能作为真实 Langflow 执行证据。" : "实际工作流完成且结果入库后，才允许人工决定。"}</span></div>
      <section className="detail-summary">
        <Tile className="score-tile"><span>规则风险分数</span><strong>{detail.risk_score ?? "未评分"}</strong><small>{detail.risk_score !== null ? "/ 100，辅助审查指标" : "处理尚未完成，不代表零风险"}</small></Tile>
        <Tile><span>负责人</span><strong>{detail.owner}</strong><small>{hasAssessment ? `${detail.pii_count} 个脱敏命中` : "脱敏结果尚未完成"}</small></Tile>
        <Tile><span>规则版本</span><strong>{hasAssessment ? detail.ruleset_version : "尚未评估"}</strong><small>确定性规则，未调用语义模型</small></Tile>
        <Tile><span>Langflow 运行</span><strong>{liveRunId ?? (detail.source_kind === "seed_demo" ? "历史演示结果" : "尚未取得运行编号")}</strong><small>{liveRunId ? "真实上游运行记录" : "不表示工作流已完成"}</small></Tile>
      </section>

      <div className="review-workflow-grid">
        <WorkflowPanel detail={detail} onRefresh={onRefresh} />
        <Tile className="decision-panel"><div className="workflow-panel-heading"><h2>人工决定</h2><StatusTag status={detail.status} /></div>{detail.decision ? <><p className="decision-result">{decisionLabels[detail.decision]}</p><p className="decision-reason">{detail.decision_reason}</p><small>{detail.decided_by}，{formatDate(detail.decided_at)}</small><p className="field-helper">决定已绑定该次文档和评估，不能原地覆盖。</p></> : <><p className="workflow-copy">{canDecide ? "已保存规则结果，请核验文档对照与风险证据后记录决定。零分案件同样需要人工决定。" : "文档处理完成、评估与当前版本一致后，才可记录人工决定。"}</p><small>演示身份：demo-reviewer</small></>}<dl className="version-reference"><dt>当前文档版本</dt><dd>{detail.current_document_version_id ?? "尚未登记"}</dd></dl></Tile>
      </div>
      <ReportPanel detail={detail} onRefresh={onRefresh} />

      {detail.warnings.length > 0 && <InlineNotification className="detail-notice" lowContrast hideCloseButton kind="warning" title="解析告警" subtitle={detail.warnings.join("；")} />}
      <div className="detail-tabs"><Tabs selectedIndex={selectedTab} onChange={({ selectedIndex }) => setSelectedTab(selectedIndex)}>
        <TabList aria-label="案件详情栏目"><Tab>规则发现</Tab><Tab>文档对照</Tab><Tab>审计记录</Tab><Tab>文档来源</Tab></TabList>
        <TabPanels>
          <TabPanel>
            <div className="findings-layout">
              <div className="finding-list">
                {!hasAssessment ? <div className="empty-state"><Renew size={32} /><h3>尚无完整规则评估</h3><p>处理未完成或失败时，不显示“未发现风险”。</p></div> : detail.findings.length ? detail.findings.map((finding) => {
                  const locator = finding.locator ?? redactedSections.find((section) => section.section_id === finding.section_id)?.locator;
                  return <Tile className="finding-item" key={`${finding.rule_id}:${finding.section_id ?? ""}:${finding.start ?? ""}`}>
                    <div className="finding-heading"><div><CodeSnippet type="inline">{finding.rule_id}</CodeSnippet><h3>{finding.title}</h3></div><RiskTag level={finding.severity} /></div>
                    <blockquote>{finding.evidence}</blockquote><p>{finding.recommendation}</p>{locator && <Button kind="ghost" size="sm" className="evidence-link" onClick={() => jumpToEvidence(finding)}>查看证据：{locator}</Button>}
                  </Tile>;
                }) : <div className="empty-state"><Checkmark size={32} /><h3>未命中当前规则</h3><p>这不代表文档无风险，仍需人工核验语义与业务背景。</p></div>}
              </div>
              <Tile className="dimension-panel"><h2>维度规则指标</h2><p className="field-helper">规则点数的派生指标，不是风险概率。</p>{hasAssessment ? Object.entries(detail.dimensions).map(([key, value]) => <div className="dimension-row" key={key}><span>{dimensionLabels[key] ?? key}</span><b>{value}</b></div>) : <p className="field-helper">尚未完成评分。</p>}</Tile>
            </div>
          </TabPanel>
          <TabPanel><div className="document-compare"><Tile><h2>原始虚构文档</h2><DocumentSections sections={parsedSections} fallback={detail.original_text} redacted={false} highlighted={null} /></Tile><Tile><h2>脱敏后文本</h2><DocumentSections sections={redactedSections} fallback={detail.redacted_text} redacted highlighted={highlightedSection} /></Tile></div></TabPanel>
          <TabPanel><div className="audit-list">{detail.audit_events.length ? detail.audit_events.map((event) => <div className="audit-item" key={event.id}><div><strong>{eventLabels[event.event_type] ?? event.event_type}</strong><span>{formatDate(event.occurred_at)}</span></div><p>{event.detail}</p><small>{event.actor}</small></div>) : <div className="empty-state"><h3>尚无审计记录</h3><p>案件处理和人工决定会追加记录。</p></div>}</div></TabPanel>
          <TabPanel><Tile className="source-panel"><h2>文档来源与指纹</h2><dl><dt>文件</dt><dd>{detail.document_name}</dd><dt>指纹类型</dt><dd>{(detail.source?.hash_kind ?? detail.hash_kind) === "synthetic_text" ? "历史虚构正文 SHA-256，不是文件字节指纹" : (detail.source?.hash_kind ?? detail.hash_kind) === "source_bytes_sha256" ? "源文件字节 SHA-256" : "指纹类型未标识"}</dd><dt>SHA-256</dt><dd>{detail.source?.source_sha256 ?? detail.document_hash}</dd><dt>真实 Langflow 运行</dt><dd>{liveRunId ?? "没有真实上游运行编号"}</dd>{detail.source?.legacy_flow_label && <><dt>历史演示标签</dt><dd>{detail.source.legacy_flow_label}（非真实运行编号）</dd></>}{detail.source?.flow_hash && <><dt>Flow 配置指纹</dt><dd>{detail.source.flow_hash}</dd></>}</dl></Tile></TabPanel>
        </TabPanels>
      </Tabs></div>

      <Modal open={dialog !== null} launcherButtonRef={decisionLauncher} modalHeading={dialog ? `记录${decisionLabels[dialog]}决定` : "记录决定"} modalLabel="演示身份：demo-reviewer" primaryButtonText={saving ? "正在保存" : "确认决定"} secondaryButtonText="取消" closeButtonLabel="关闭决定窗口" onRequestClose={() => { if (!saving) setDialog(null); }} onRequestSubmit={submitDecision} primaryButtonDisabled={saving || reasonLength < 8 || reasonLength > 1000 || !canDecide} danger={dialog === "rejected"} hasScrollingContent preventCloseOnClickOutside>
        <p className="modal-copy">决定将绑定当前文档与评估版本，写入审计并登记独立的报告任务。</p>
        <TextArea id="decision-reason" labelText="决定理由" helperText={`去除首尾空白后须为 8-1000 个字符，当前 ${reasonLength} 个。请说明核验依据或所需修改。`} value={reason} disabled={saving} maxLength={2000} onChange={(event) => { setReason(event.target.value); decisionKey.current = crypto.randomUUID(); setSaveError(null); }} invalid={reason.length > 0 && (reasonLength < 8 || reasonLength > 1000)} invalidText="去除首尾空白后，决定理由须为 8-1000 个字符。" />
        <div className="decision-choice-row"><Button size="sm" disabled={saving} kind={dialog === "approved" ? "primary" : "tertiary"} onClick={() => selectDecision("approved")}>批准</Button><Button size="sm" disabled={saving} kind={dialog === "changes_requested" ? "primary" : "tertiary"} onClick={() => selectDecision("changes_requested")} renderIcon={Renew}>要求修改</Button><Button size="sm" disabled={saving} kind={dialog === "rejected" ? "danger" : "danger--tertiary"} onClick={() => selectDecision("rejected")} renderIcon={WarningAlt}>驳回</Button></div>
        {saveError && <InlineNotification lowContrast kind="error" hideCloseButton title="保存失败" subtitle={saveError} />}
      </Modal>
    </>
  );
}
