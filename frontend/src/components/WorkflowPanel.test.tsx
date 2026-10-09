import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { jsonResponse, makeDetail } from "../test/fixtures";
import { WorkflowPanel } from "./WorkflowPanel";

afterEach(() => vi.unstubAllGlobals());

test("recoverable failed intake retries the active document and failed job only", async () => {
  const fetch = vi.fn((_: RequestInfo | URL, _init?: RequestInit) => Promise.resolve(jsonResponse({ job_id: "retry-2", state: "queued", kind: "intake", phase: "queued", attempt: 0 }, 202)));
  vi.stubGlobal("fetch", fetch);
  const refresh = vi.fn(async () => {});
  const detail = makeDetail({ status: "failed", risk_score: null, risk_level: null, assessment_id: null, jobs: [{ job_id: "failed-intake", kind: "intake", state: "failed", phase: "failed", attempt: 3, error_code: "langflow_auth_failed", retryable: true }] });
  render(<WorkflowPanel detail={detail} onRefresh={refresh} />);
  expect(screen.getByText("Langflow 身份验证失败，请检查服务端配置后重试。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重试文档处理" }));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  const init = fetch.mock.calls[0][1] as RequestInit;
  expect(JSON.parse(init.body as string)).toEqual({ document_version_id: "version-1", job_id: "failed-intake" });
  expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
});

test("input failures need a new supported document and automatic retry waits do not allow duplicate retry", () => {
  const detail = makeDetail({ status: "failed", risk_score: null, risk_level: null, assessment_id: null, jobs: [{ job_id: "failed-intake", kind: "intake", state: "failed", phase: "failed", attempt: 1, error_code: "requires_ocr", retryable: false }] });
  const { rerender } = render(<WorkflowPanel detail={detail} onRefresh={vi.fn(async () => {})} />);
  expect(screen.queryByRole("button", { name: "重试文档处理" })).not.toBeInTheDocument();
  expect(screen.getByText(/当前版本暂不支持 OCR/)).toBeInTheDocument();
  rerender(<WorkflowPanel detail={{ ...detail, status: "processing", jobs: [{ ...detail.jobs[0], state: "retry_wait", error_code: "langflow_unavailable", retryable: false }] }} onRefresh={vi.fn(async () => {})} />);
  expect(screen.getByText(/系统将按策略自动重试/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "重试文档处理" })).not.toBeInTheDocument();
});
