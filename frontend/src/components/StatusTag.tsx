import { Tag } from "@carbon/react";

const labels: Record<string, string> = {
  pending_approval: "待人工审批",
  approved: "已批准",
  rejected: "已驳回",
  changes_requested: "要求修改",
  ready: "历史就绪状态",
  received: "等待处理",
  processing: "处理中",
  failed: "处理失败",
};

const types: Record<string, "blue" | "green" | "red" | "purple" | "gray"> = {
  pending_approval: "blue",
  approved: "green",
  rejected: "red",
  changes_requested: "purple",
  ready: "gray",
  received: "gray",
  processing: "blue",
  failed: "red",
};

export function StatusTag({ status }: { status: string }) {
  return <Tag type={types[status] ?? "gray"}>{labels[status] ?? status}</Tag>;
}

export function RiskTag({ level }: { level: string | null }) {
  if (!level) return <Tag type="gray">尚未评分</Tag>;
  const type =
    level === "critical" ? "red" : level === "high" ? "magenta" : level === "medium" ? "warm-gray" : level === "low" ? "green" : "gray";
  const label = { critical: "严重", high: "高", medium: "中", low: "低" }[level] ?? level;
  return <Tag type={type}>{label}风险</Tag>;
}
