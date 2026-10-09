import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import { jsonResponse, makeDetail, testSummary, testSystemStatus } from "./test/fixtures";

const summary = { ...testSummary, total_cases: 12 };
const cases = [makeDetail()];

beforeEach(() => {
  history.replaceState(null, "", "/");
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => Promise.resolve(jsonResponse(String(input).endsWith("/summary") ? summary : String(input).endsWith("/system/status") ? testSystemStatus : cases))));
});

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); history.replaceState(null, "", "/"); });

test("renders the Langflow attribution and dashboard data", async () => {
  render(<App />);
  expect(screen.getByText("Built on Langflow")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("文档风险与决策")).toBeInTheDocument());
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText("虚构协议")).toBeInTheDocument();
  expect(screen.getByText("不可用")).toBeInTheDocument();
  expect(screen.getByText("未取得上游响应")).toBeInTheDocument();
});

test("missing health probes stay unknown even when the old summary declares healthy", async () => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => Promise.resolve(String(input).endsWith("/system/status") ? jsonResponse({ code: "status_unavailable", detail: "No probes" }, 503) : jsonResponse(String(input).endsWith("/summary") ? summary : cases))));
  render(<App />);
  await screen.findByRole("heading", { name: "文档风险与决策" });
  expect(screen.getAllByText("未知")).toHaveLength(4);
  expect(screen.queryByText("正常")).not.toBeInTheDocument();
});

test("a processing case restores from its link, polls every two seconds and stops at a terminal review state", async () => {
  vi.useFakeTimers();
  Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
  history.replaceState(null, "", "#case/RC-TEST");
  let detailRequests = 0;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = String(input);
    if (path.endsWith("/cases/RC-TEST")) {
      detailRequests += 1;
      return Promise.resolve(jsonResponse(detailRequests === 1 ? makeDetail({ status: "processing", risk_score: null, risk_level: null, assessment_id: null, jobs: [{ job_id: "job-1", kind: "intake", state: "running", phase: "parsing", attempt: 1, error_code: null, retryable: false }] }) : makeDetail()));
    }
    return Promise.resolve(jsonResponse(path.endsWith("/summary") ? summary : path.endsWith("/system/status") ? testSystemStatus : cases));
  }));
  const { unmount } = render(<App />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(detailRequests).toBe(1);
  expect(screen.getByRole("button", { name: "记录决定" })).toBeDisabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
  expect(detailRequests).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(detailRequests).toBe(2);
  expect(screen.getByRole("button", { name: "记录决定" })).toBeEnabled();
  await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
  expect(detailRequests).toBe(2);
  unmount();
});

test("hidden pages slow polling and unmount aborts active requests", async () => {
  vi.useFakeTimers();
  let hidden = false;
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  history.replaceState(null, "", "#case/RC-TEST");
  let detailRequests = 0;
  const signals: AbortSignal[] = [];
  const processing = makeDetail({ status: "processing", risk_score: null, risk_level: null, assessment_id: null, jobs: [{ job_id: "job-1", kind: "intake", state: "running", phase: "parsing", attempt: 1, error_code: null, retryable: false }] });
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.signal) signals.push(init.signal);
    const path = String(input);
    if (path.endsWith("/cases/RC-TEST")) { detailRequests += 1; return Promise.resolve(jsonResponse(processing)); }
    return Promise.resolve(jsonResponse(path.endsWith("/summary") ? summary : path.endsWith("/system/status") ? testSystemStatus : [processing]));
  }));
  const { unmount } = render(<App />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  hidden = true;
  fireEvent(document, new Event("visibilitychange"));
  await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
  expect(detailRequests).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(13_000); });
  expect(detailRequests).toBe(2);
  unmount();
  expect(signals.every((signal) => signal.aborted)).toBe(true);
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  expect(detailRequests).toBe(2);
});
