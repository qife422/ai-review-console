// Vitest resolves these native test-host modules. Browser tsconfig intentionally has no Node types.
// @ts-expect-error Test-host built-in; never imported by the browser bundle.
import { Blob as NodeBlob } from "node:buffer";
// @ts-expect-error Test-host built-in; never imported by the browser bundle.
import { webcrypto } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createDemoSandbox, DEMO_NOTICE, DEMO_SAMPLES } from "./index";

const reason = "已核验全部虚构责任条款，仅用于本页流程演示。";
async function hash(text: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-28T12:00:00Z"));
  vi.stubGlobal("crypto", webcrypto);
  vi.stubGlobal("Blob", NodeBlob);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Sandbox must not send requests"); }));
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("No browser storage"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("No browser storage"); });
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("synthetic browser sandbox", () => {
  it("loads only labelled presets and never advertises actual upstream execution", async () => {
    const { api } = createDemoSandbox();
    expect((await api.cases()).length).toBe(4);
    const initial = await api.case("RC-BROWSER-001");
    expect(initial.source_kind).toBe("seed_demo");
    expect(initial.hash_kind).toBe("synthetic_text");
    expect(initial.flow_run_id).toBeNull();
    expect(initial.jobs[0].langflow_job_id).toBeNull();
    expect(initial.source?.flow_id).toBeNull();
    expect(initial.document_hash).toBe(await hash(DEMO_SAMPLES[0].text));
    expect((await api.case("RC-BROWSER-004")).status).toBe("pending_approval");
    expect((await api.case("RC-BROWSER-004")).risk_score).toBe(0);
    expect((await api.systemStatus()).services.langflow).toMatchObject({ state: "unknown", detail: "前端沙盒，未连接真实服务" });
    expect(api.reportUrl(initial.id, "html")).not.toContain("/api");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a device file even with matching name and synthetic marker without reading it", async () => {
    const { api } = createDemoSandbox();
    const file = new File([DEMO_SAMPLES[0].text], DEMO_SAMPLES[0].filename, { type: "text/plain" });
    const read = vi.fn(() => { throw new Error("Foreign file must not be read"); });
    Object.defineProperty(file, "text", { value: read });
    await expect(api.upload(file, DEMO_SAMPLES[0].title, "foreign-file")).rejects.toMatchObject({ code: "demo_files_not_allowed", status: 422 });
    expect(read).not.toHaveBeenCalled();
    expect((await api.cases()).length).toBe(4);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("advances preset submissions through unknown score, processing, and manual review", async () => {
    const sandbox = createDemoSandbox();
    const accepted = await sandbox.api.upload(sandbox.createDemoFile("privacy"), DEMO_SAMPLES[1].title, "preset-upload");
    const received = await sandbox.api.case(accepted.case_id);
    expect(received.status).toBe("received");
    expect(received.risk_score).toBeNull();
    expect(received.assessment_id).toBeNull();
    await vi.advanceTimersByTimeAsync(800);
    expect((await sandbox.api.case(accepted.case_id)).jobs[0]).toMatchObject({ state: "running", phase: "parsing" });
    await vi.advanceTimersByTimeAsync(2300);
    const scored = await sandbox.api.case(accepted.case_id);
    expect(scored.status).toBe("pending_approval");
    expect(scored.risk_score).toBe(50);
    expect(scored.redacted_text).toContain("[PERSON_01]");
    expect(scored.redacted_text).not.toContain("13800138001");
    expect(scored.source?.langflow_job_id).toBeNull();
    const evidence = scored.findings[0];
    expect([...scored.redacted_text].slice(evidence.start!, evidence.end!).join("")).toBe(evidence.evidence);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("deduplicates concurrent preset submission keys and rejects changed key content", async () => {
    const sandbox = createDemoSandbox();
    const file = sandbox.createDemoFile("liability");
    const [first, second] = await Promise.all([sandbox.api.upload(file, DEMO_SAMPLES[0].title, "same-key"), sandbox.api.upload(file, DEMO_SAMPLES[0].title, "same-key")]);
    expect(first.case_id).toBe(second.case_id);
    expect((await sandbox.api.cases()).length).toBe(5);
    await expect(sandbox.api.upload(sandbox.createDemoFile("clean"), DEMO_SAMPLES[3].title, "same-key")).rejects.toMatchObject({ code: "idempotency_conflict" });
    await expect(sandbox.api.upload(file, "arbitrary text", "another-key")).rejects.toMatchObject({ code: "demo_sample_invalid" });
  });

  it("enforces review reason, identity, assessment, version, and row version", async () => {
    const { api } = createDemoSandbox();
    const original = await api.case("RC-BROWSER-001");
    await expect(api.decide(original, "approved", "        ", "demo-reviewer", "empty")).rejects.toMatchObject({ status: 422 });
    await expect(api.decide(original, "approved", reason, "", "identity")).rejects.toMatchObject({ status: 422 });
    for (const stale of [{ ...original, row_version: original.row_version + 1 }, { ...original, assessment_id: "other" }, { ...original, current_document_version_id: "other" }]) {
      await expect(api.decide(stale, "approved", reason, "demo-reviewer", "stale")).rejects.toMatchObject({ code: "decision_conflict", status: 409 });
    }
    expect((await api.case(original.id)).decision).toBeNull();
  });

  it("records only one concurrent decision and permits exact idempotent replay", async () => {
    const { api } = createDemoSandbox();
    const original = await api.case("RC-BROWSER-001");
    const result = await Promise.allSettled([api.decide(original, "approved", reason, "demo-reviewer", "first"), api.decide(original, "rejected", reason, "demo-reviewer", "second")]);
    expect(result.filter((item) => item.status === "fulfilled")).toHaveLength(1);
    expect(result.filter((item) => item.status === "rejected")).toHaveLength(1);
    const saved = await api.case(original.id);
    expect(saved.audit_events.filter((item) => item.event_type === "decision_recorded")).toHaveLength(1);
    expect(saved.jobs.filter((item) => item.kind === "report")).toHaveLength(1);
    const winnerKey = saved.decision === "approved" ? "first" : "second";
    await expect(api.decide(original, saved.decision!, reason, "demo-reviewer", winnerKey)).resolves.toMatchObject({ decision: saved.decision });
    await expect(api.decide(original, saved.decision!, reason + "已变化", "demo-reviewer", winnerKey)).rejects.toMatchObject({ code: "idempotency_conflict" });
  });

  it.each(["approved", "rejected", "changes_requested"] as const)("generates version-bound %s JSON and escaped printable HTML with actual byte hashes", async (decision) => {
    const { api } = createDemoSandbox();
    const original = await api.case("RC-BROWSER-001");
    await expect(api.downloadReport(original.id, "json", `BR-${original.id}-json`)).rejects.toMatchObject({ code: "report_not_ready" });
    const injection = '<img src=x onerror="alert(1)">已核验虚构责任条款。';
    const saved = await api.decide(original, decision, injection, "demo-reviewer", "decision-key");
    expect(saved.reports.every((item) => item.state === "queued")).toBe(true);
    await vi.advanceTimersByTimeAsync(2000);
    const ready = await api.case(original.id);
    expect(ready.reports.map((item) => item.format)).toEqual(["json", "html"]);
    expect(ready.reports.every((item) => item.state === "ready")).toBe(true);
    for (const artifact of ready.reports) {
      const first = await api.downloadReport(original.id, artifact.format, artifact.report_id);
      const text = await first.text();
      expect(await hash(text)).toBe(artifact.sha256);
      expect(new TextEncoder().encode(text).byteLength).toBe(artifact.bytes);
      expect(await (await api.downloadReport(original.id, artifact.format, artifact.report_id)).text()).toBe(text);
      expect(text).toContain("SYNTHETIC DEMO DATA ONLY");
      if (artifact.format === "json") expect(JSON.parse(text)).toMatchObject({ decision, case_id: original.id, document_version_id: original.current_document_version_id, real_langflow_run_id: null, reason: injection });
      else { expect(text).toContain("&lt;img"); expect(text).not.toMatch(/<(?:script|img)\b/i); }
    }
    await expect(api.downloadReport(original.id, "pdf", `BR-${original.id}-pdf`)).rejects.toMatchObject({ code: "report_not_ready" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("keeps visitor stores independent, returns copies, and fully resets local state", async () => {
    const one = createDemoSandbox();
    const two = createDemoSandbox();
    const original = await one.api.case("RC-BROWSER-001");
    original.findings[0].title = "mutated client copy";
    expect((await one.api.case(original.id)).findings[0].title).not.toBe("mutated client copy");
    await one.api.decide(await one.api.case(original.id), "approved", reason, "demo-reviewer", "decision");
    expect((await two.api.case(original.id)).decision).toBeNull();
    const oldFile = one.createDemoFile("privacy");
    const created = await one.api.upload(oldFile, DEMO_SAMPLES[1].title, "upload");
    one.reset();
    await vi.advanceTimersByTimeAsync(5000);
    expect((await one.api.summary()).total_cases).toBe(4);
    expect((await one.api.case(original.id)).decision).toBeNull();
    expect((await one.api.case(original.id)).reports).toEqual([]);
    await expect(one.api.case(created.case_id)).rejects.toMatchObject({ status: 404 });
    await expect(one.api.upload(oldFile, DEMO_SAMPLES[1].title, "old-file")).rejects.toMatchObject({ code: "demo_files_not_allowed" });
    expect(vi.getTimerCount()).toBe(0);
    expect(DEMO_NOTICE).toContain("非真实");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects aborted operations without creating state", async () => {
    const sandbox = createDemoSandbox();
    const controller = new AbortController(); controller.abort();
    await expect(sandbox.api.upload(sandbox.createDemoFile("clean"), DEMO_SAMPLES[3].title, "aborted", controller.signal)).rejects.toMatchObject({ name: "AbortError" });
    expect((await sandbox.api.summary()).total_cases).toBe(4);
  });

  it.each(["upload", "decision"])("cannot resurrect an in-flight %s after resetting during SHA calculation", async (operation) => {
    const sandbox = createDemoSandbox();
    const detail = await sandbox.api.case("RC-BROWSER-001");
    const originalDigest = crypto.subtle.digest.bind(crypto.subtle);
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => { release = resolve; });
    const digest = vi.spyOn(crypto.subtle, "digest").mockImplementationOnce(async (algorithm, data) => {
      await blocked;
      return originalDigest(algorithm, data);
    });
    const pending = operation === "upload" ? sandbox.api.upload(sandbox.createDemoFile("clean"), DEMO_SAMPLES[3].title, "reset-upload") : sandbox.api.decide(detail, "approved", reason, "demo-reviewer", "reset-decision");
    for (let count = 0; count < 12 && !digest.mock.calls.length; count += 1) await Promise.resolve();
    expect(digest).toHaveBeenCalledOnce();
    sandbox.reset();
    release();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect((await sandbox.api.summary()).total_cases).toBe(4);
    expect((await sandbox.api.case(detail.id)).decision).toBeNull();
    expect((await sandbox.api.case(detail.id)).reports).toEqual([]);
  });
});
