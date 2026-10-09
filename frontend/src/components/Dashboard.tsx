import { ArrowRight, CheckmarkOutline, Document, Pending, WarningAlt } from "@carbon/icons-react";
import { Button, ClickableTile, InlineNotification, SkeletonText, Tag, Tile } from "@carbon/react";
import type { CaseSummary, DashboardSummary, SystemStatus } from "../types";
import { formatDate } from "../workflow";
import { RiskTag, StatusTag } from "./StatusTag";

interface DashboardProps {
  summary: DashboardSummary | null;
  systemStatus: SystemStatus | null;
  cases: CaseSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectCase: (id: string) => void;
  onOpenQueue: () => void;
}

const categoryLabels: Record<string, string> = {
  privacy: "隐私",
  legal: "法律条款",
  financial: "财务",
  security: "信息安全",
  policy: "内部政策",
};

export function Dashboard({ summary, systemStatus, cases, loading, error, onRetry, onSelectCase, onOpenQueue }: DashboardProps) {
  if (error) {
    return <div className="error-state"><InlineNotification kind="error" title="无法加载审查总览" subtitle={error} /><Button size="sm" onClick={onRetry}>重试</Button></div>;
  }
  if (loading || !summary) {
    return <div className="loading-grid" aria-label="正在加载总览"><SkeletonText heading /><SkeletonText paragraph lineCount={6} /></div>;
  }

  const metrics = [
    { label: "全部案件", value: summary.total_cases, icon: Document, meta: "历史演示及新增虚构文档" },
    { label: "待人工审批", value: summary.pending_approval, icon: Pending, meta: "需要审查员决定" },
    { label: "高风险案件", value: summary.high_risk, icon: WarningAlt, meta: "高或严重风险" },
    { label: "已形成决定", value: summary.completed, icon: CheckmarkOutline, meta: "包含三种决定类型" },
  ];

  return (
    <>
      <section className="page-heading">
        <div>
          <p className="section-label">审查运营总览</p>
          <h1 tabIndex={-1}>文档风险与决策</h1>
          <p>确定性规则负责解释风险，最终决定始终由人工完成。</p>
        </div>
        <Button renderIcon={ArrowRight} onClick={onOpenQueue}>打开审查队列</Button>
      </section>

      <section className="metric-grid" aria-label="关键指标">
        {metrics.map(({ label, value, icon: Icon, meta }) => (
          <Tile className="metric-tile" key={label}>
            <div className="metric-icon"><Icon size={20} /></div>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{meta}</small>
          </Tile>
        ))}
      </section>

      <section className="analysis-grid">
        <Tile className="analysis-panel">
          <div className="panel-heading"><div><h2>风险等级分布</h2><p>{summary.scored_cases ?? Object.values(summary.risk_distribution).reduce((sum, count) => sum + count, 0)} 个已完成评分的虚构案件</p></div><div className="average-score"><strong>{summary.average_score ?? "未评分"}</strong><small>平均规则分</small></div></div>
          <div className="distribution-list">
            {(["critical", "high", "medium", "low"] as const).map((level) => {
              const count = summary.risk_distribution[level];
              const scored = summary.scored_cases ?? Object.values(summary.risk_distribution).reduce((sum, value) => sum + value, 0);
              const width = scored ? `${(count / scored) * 100}%` : "0%";
              return <div className="distribution-row" key={level}><RiskTag level={level} /><div className="thin-bar" aria-label={`${level} ${count}`}><span className={`bar-${level}`} style={{ width }} /></div><b>{count}</b></div>;
            })}
          </div>
        </Tile>
        <Tile className="analysis-panel category-panel">
          <div className="panel-heading"><div><h2>主要风险类别</h2><p>按规则命中次数统计</p></div></div>
          <div className="category-grid">
            {Object.entries(summary.category_distribution).map(([key, value]) => (
              <div key={key}><span>{categoryLabels[key] ?? key}</span><strong>{value}</strong><small>条发现</small></div>
            ))}
          </div>
        </Tile>
      </section>

      <section className="recent-section">
        <div className="section-heading"><div><h2>最近需要关注</h2><p>优先展示待审批和高风险案件。</p></div><Button kind="ghost" size="sm" onClick={onOpenQueue}>查看全部</Button></div>
        <div className="recent-grid">
          {cases.slice(0, 4).map((item) => (
            <ClickableTile key={item.id} onClick={() => onSelectCase(item.id)} className="case-tile">
              <div className="case-tile-top"><span>{item.id}</span><RiskTag level={item.risk_level} /></div>
              <h3>{item.title}</h3>
              <p>{item.document_name}</p>
              <div className="case-tile-footer"><StatusTag status={item.status} /><strong>{item.risk_score ?? "未评分"}{item.risk_score !== null && <small>/100</small>}</strong></div>
            </ClickableTile>
          ))}
        </div>
        {cases.length === 0 && <div className="empty-state attention-empty"><CheckmarkOutline size={32} /><h3>当前没有待关注案件</h3><p>上传的新文档完成处理后均会进入人工审批。</p></div>}
      </section>

      <section className="system-section" aria-label="实际运行状态">
        <div className="section-heading"><div><h2>运行状态</h2><p>探测时间：{formatDate(systemStatus?.checked_at)}</p></div><Button kind="ghost" size="sm" onClick={onRetry}>检查状态</Button></div>
        <div className="system-grid">{Object.entries({ api: "Review API", database: "数据库", worker: "后台 Worker", langflow: "Langflow" }).map(([key, label]) => {
          const probe = systemStatus?.services[key];
          const state = probe?.state ?? "unknown";
          const stateLabels = { healthy: "正常", degraded: "降级", unavailable: "不可用", unknown: "未知" };
          return <div key={key}><strong>{label}</strong><Tag type={state === "healthy" ? "green" : state === "unavailable" ? "red" : state === "degraded" ? "warm-gray" : "gray"}>{stateLabels[state] ?? "未知"}</Tag><small>{probe?.detail || (state === "unknown" ? "尚未取得有效探测结果" : `检查于 ${formatDate(probe?.checked_at ?? systemStatus?.checked_at)}`)}</small></div>;
        })}</div>
      </section>
    </>
  );
}
