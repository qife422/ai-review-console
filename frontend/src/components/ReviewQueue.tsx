import { Search, Upload } from "@carbon/icons-react";
import {
  Button,
  DataTable,
  DataTableSkeleton,
  Dropdown,
  InlineNotification,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
} from "@carbon/react";
import { useMemo, useState } from "react";
import type { CaseSummary } from "../types";
import { RiskTag, StatusTag } from "./StatusTag";
import { isPublicDemo } from "../demoMode";

interface ReviewQueueProps {
  cases: CaseSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectCase: (id: string) => void;
  onUpload: () => void;
}

const headers = [
  { key: "case", header: "案件" },
  { key: "risk", header: "风险" },
  { key: "status", header: "状态" },
  { key: "owner", header: "负责人" },
  { key: "submitted", header: "提交时间" },
];
const riskItems = [{ id: "all", text: "全部风险" }, { id: "critical", text: "严重" }, { id: "high", text: "高" }, { id: "medium", text: "中" }, { id: "low", text: "低" }];

export function ReviewQueue({ cases, loading, error, onRetry, onSelectCase, onUpload }: ReviewQueueProps) {
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("all");
  const filtered = useMemo(
    () => cases.filter((item) =>
      (risk === "all" || item.risk_level === risk) &&
      `${item.id}${item.title}${item.document_name}`.toLowerCase().includes(query.toLowerCase())),
    [cases, query, risk],
  );
  const rows = filtered.map((item) => ({
    id: item.id,
    case: item.title,
    risk: item.risk_level,
    status: item.status,
    owner: item.owner,
    submitted: new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(item.submitted_at)),
  }));

  return (
    <>
      <section className="page-heading compact"><div><p className="section-label">人工决策工作区</p><h1 tabIndex={-1}>审查队列</h1><p>{isPublicDemo ? "载入预置虚构样本，体验审查与人工决定。" : "上传虚构文档、查看处理结果并记录人工决定。"}</p></div><Button renderIcon={Upload} onClick={onUpload}>{isPublicDemo ? "载入虚构样本" : "上传虚构文档"}</Button></section>
      {error && <div className="queue-error"><InlineNotification kind="error" lowContrast hideCloseButton title="队列更新失败" subtitle={error} /><Button kind="tertiary" size="sm" onClick={onRetry}>重新加载</Button></div>}
      {loading ? <DataTableSkeleton columnCount={5} rowCount={8} /> : (
        <DataTable rows={rows} headers={headers}>
          {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => (
            <TableContainer className="queue-table" title="全部审查案件" description={`${filtered.length} 个虚构演示案件`}>
              <TableToolbar>
                <TableToolbarContent>
                  <TableToolbarSearch persistent value={query} onChange={(_, value) => setQuery(value ?? "")} placeholder="搜索案件或文件" />
                  <Dropdown id="risk-filter" label="风险等级" aria-label="风险等级" titleText="" size="lg" items={riskItems} itemToString={(item) => item?.text ?? ""} selectedItem={riskItems.find((item) => item.id === risk) ?? riskItems[0]} onChange={({ selectedItem }) => setRisk(selectedItem?.id ?? "all")} />
                </TableToolbarContent>
              </TableToolbar>
              <Table {...getTableProps()}>
                <TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead>
                <TableBody>
                  {tableRows.map((row) => {
                    const item = cases.find((entry) => entry.id === row.id);
                    if (!item) return null;
                    return <TableRow {...getRowProps({ row })} key={row.id} onClick={() => onSelectCase(row.id)} className="clickable-row" tabIndex={0} aria-label={`查看案件：${item.title}`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectCase(row.id); } }}>
                      <TableCell><div className="case-cell"><strong>{item.title}</strong><span>{item.id} / {item.document_type}</span><small>{item.source_kind === "uploaded_demo" ? "新增虚构文档" : item.source_kind === "seed_demo" ? "历史种子演示" : "来源未标识"}</small></div></TableCell>
                      <TableCell><div className="risk-cell"><b>{item.risk_score ?? "未评分"}</b><RiskTag level={item.risk_level} /></div></TableCell>
                      <TableCell><StatusTag status={item.status} /></TableCell>
                      <TableCell>{item.owner}</TableCell>
                      <TableCell>{row.cells.find((cell) => cell.info.header === "submitted")?.value}</TableCell>
                    </TableRow>;
                  })}
                </TableBody>
              </Table>
              {filtered.length === 0 && <div className="empty-state"><Search size={32} /><h3>{cases.length ? "没有匹配案件" : "尚无审查案件"}</h3><p>{cases.length ? "调整搜索内容或风险筛选条件。" : "使用“上传虚构文档”提交第一份演示文档。"}</p></div>}
            </TableContainer>
          )}
        </DataTable>
      )}
    </>
  );
}
