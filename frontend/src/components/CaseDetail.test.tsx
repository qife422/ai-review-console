import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { jsonResponse, makeDetail } from "../test/fixtures";
import type { CaseDetail as Detail } from "../types";
import { CaseDetail } from "./CaseDetail";

function renderDetail(detail: Detail, onRefresh = vi.fn(async () => {}), onDecided = vi.fn()) {
  return render(<CaseDetail detail={detail} loading={false} error={null} onBack={vi.fn()} onReload={vi.fn()} onRefresh={onRefresh} onDecided={onDecided} onDismissNotice={vi.fn()} />);
}

afterEach(() => vi.unstubAllGlobals());

test("unfinished review does not appear as zero risk and cannot be decided or exported", () => {
  renderDetail(makeDetail({ status: "processing", risk_score: null, risk_level: null, assessment_id: null, findings: [], jobs: [] }));
  expect(screen.getByRole("button", { name: "记录决定" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "下载 PDF" })).toBeDisabled();
  expect(screen.getByText("处理尚未完成，不代表零风险")).toBeInTheDocument();
  expect(screen.getByText("尚无完整规则评估")).toBeInTheDocument();
  expect(screen.queryByText("未命中当前规则")).not.toBeInTheDocument();
});

test("a complete zero rule score still requires a version-bound human decision", async () => {
  const detail = makeDetail({ risk_score: 0, risk_level: "low", findings: [] });
  const decided = vi.fn();
  const fetch = vi.fn((_: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(jsonResponse({ ...detail, status: "approved", decision: "approved" })));
  vi.stubGlobal("fetch", fetch);
  renderDetail(detail, undefined, decided);
  expect(screen.getByRole("button", { name: "记录决定" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "下载 PDF" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "记录决定" }));
  expect(screen.getByLabelText("决定理由")).toHaveFocus();
  fireEvent.change(screen.getByLabelText("决定理由"), { target: { value: "   1234567   " } });
  expect(screen.getByRole("button", { name: "确认决定" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("决定理由"), { target: { value: "  已核验虚构条款并确认。  " } });
  fireEvent.click(screen.getByRole("button", { name: "确认决定" }));
  await waitFor(() => expect(decided).toHaveBeenCalled());
  const init = fetch.mock.calls[0][1] as RequestInit;
  expect(JSON.parse(init.body as string)).toEqual({ decision: "approved", reason: "已核验虚构条款并确认。", document_version_id: "version-1", assessment_id: "assessment-1", expected_row_version: 3 });
  expect(new Headers(init.headers).get("X-Reviewer")).toBe("demo-reviewer");
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
});

test("a concurrent decision conflict refreshes the existing result without overwriting it", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(jsonResponse({ code: "decision_conflict", detail: "Already decided", retryable: false }, 409))));
  const refresh = vi.fn(async () => {});
  const decided = vi.fn();
  renderDetail(makeDetail(), refresh, decided);
  fireEvent.click(screen.getByRole("button", { name: "记录决定" }));
  fireEvent.change(screen.getByLabelText("决定理由"), { target: { value: "已核验全部虚构条款。" } });
  fireEvent.click(screen.getByRole("button", { name: "确认决定" }));
  await screen.findByText("决定冲突");
  expect(refresh).toHaveBeenCalledOnce();
  expect(decided).not.toHaveBeenCalled();
  expect(document.querySelector('.cds--modal.is-visible [role="dialog"]')).toBeNull();
});

test("only ready formats download and a report retry excludes completed artifacts", async () => {
  const detail = makeDetail({ status: "approved", decision: "approved", decision_reason: "已核验全部虚构条款。", reports: [
    { report_id: "r-json", format: "json", state: "ready", snapshot_hash: "snapshot-1", sha256: "c".repeat(64), bytes: 200, created_at: "2026-10-08T12:01:00Z" },
    { report_id: "r-html", format: "html", state: "failed", snapshot_hash: "snapshot-1", sha256: null, bytes: null, created_at: null },
    { report_id: "r-pdf", format: "pdf", state: "missing", snapshot_hash: "snapshot-1", sha256: null, bytes: null, created_at: null },
  ] });
  const fetch = vi.fn((_: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(jsonResponse({ case_id: detail.id, document_version_id: "version-1", job_id: "report-job-2", status: "queued" }, 202)));
  vi.stubGlobal("fetch", fetch);
  const refresh = vi.fn(async () => {});
  renderDetail(detail, refresh);
  expect(screen.getByRole("button", { name: "下载 JSON" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "下载 PDF" })).toBeDisabled();
  expect(screen.getByText("部分格式可用")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重试未完成格式" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  const init = fetch.mock.calls[0][1] as RequestInit;
  expect(JSON.parse(init.body as string)).toEqual({ snapshot_hash: "snapshot-1", formats: ["html", "pdf"] });
});

test("a historical source label is never presented as a real Langflow run", () => {
  const detail = makeDetail({ source_kind: "seed_demo", flow_run_id: null, jobs: [], source: { source_sha256: "a".repeat(64), hash_kind: "synthetic_text", bytes: null, mime_type: null, source_kind: "seed_demo", legacy_flow_label: "lf-demo-0001", langflow_job_id: null, flow_id: null, flow_hash: null } });
  renderDetail(detail);
  const runTile = screen.getByText("Langflow 运行").closest(".cds--tile")!;
  expect(within(runTile as HTMLElement).getByText("历史演示结果")).toBeInTheDocument();
  expect(within(runTile as HTMLElement).queryByText("lf-demo-0001")).not.toBeInTheDocument();
  expect(screen.getByText("历史虚构种子案例，结果用于演示；不表示已执行真实 Intake Flow。")).toBeInTheDocument();
});

test("a failed report integrity check remains an in-page error and does not change the human decision", async () => {
  const fetch = vi.fn((_: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(jsonResponse({ code: "report_integrity_invalid", detail: "Integrity mismatch", retryable: false }, 409)));
  vi.stubGlobal("fetch", fetch);
  const decided = vi.fn();
  renderDetail(makeDetail({ status: "approved", decision: "approved", reports: [{ report_id: "r-pdf", format: "pdf", state: "ready", snapshot_hash: "snapshot-1", sha256: "c".repeat(64), bytes: 1000, created_at: "2026-10-08T12:01:00Z" }] }), undefined, decided);
  fireEvent.click(screen.getByRole("button", { name: "下载 PDF" }));
  await screen.findByText("报告字节与登记指纹不一致，下载已停止。请核对运行产物。");
  expect(fetch.mock.calls[0][0]).toBe("/api/cases/RC-TEST/report/pdf?report_id=r-pdf");
  expect(screen.getByRole("button", { name: "记录决定" })).toBeDisabled();
  expect(decided).not.toHaveBeenCalled();
});

test("evidence navigation selects and focuses the matching redacted section", async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  renderDetail(makeDetail());
  fireEvent.click(screen.getByRole("button", { name: "查看证据：block:1" }));
  await waitFor(() => expect(document.activeElement).toHaveAttribute("id", "evidence-section-section-1"));
  expect(screen.getByRole("tab", { name: "文档对照" })).toHaveAttribute("aria-selected", "true");
});
