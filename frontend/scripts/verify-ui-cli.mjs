/**
 * CLI-only browser acceptance. No Playwright SDK / @playwright/test dependency.
 * Requires the published local synthetic-only stack and a Chromium browser.
 * Defaults to an independent upload + Intake, without a human decision.
 * ARC_UI_APPROVE=1 explicitly enables the decision / three-format report path.
 * Browser-only mocked failures are identified separately from real workflows.
 * All generated inputs, snapshots, logs and downloads stay in a fresh temp root.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

const origin = new URL(process.env.ARC_UI_BASE_URL ?? "http://localhost:8080");
assert(["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname), "Only a local synthetic test stack is allowed");
const approve = process.env.ARC_UI_APPROVE === "1";
const intake = process.env.ARC_UI_INTAKE !== "0";
function evidenceDirectory() {
  const requested = process.env.ARC_UI_EVIDENCE_DIR;
  if (!requested) return mkdtempSync(join(tmpdir(), "arc-ui-cli-"));
  assert(isAbsolute(requested), "ARC_UI_EVIDENCE_DIR must be absolute");
  assert(!existsSync(requested), "ARC_UI_EVIDENCE_DIR must not already exist; never overwrite evidence");
  const directory = join(realpathSync(dirname(resolve(requested))), basename(requested));
  const roots = [tmpdir(), "/tmp", process.env.RUNNER_TEMP].filter((root) => root && existsSync(root)).map((root) => realpathSync(root));
  assert(roots.some((root) => directory.startsWith(`${root}${sep}`)), "Evidence directory must be a new child of system temp or RUNNER_TEMP");
  mkdirSync(directory);
  return directory;
}
const evidence = evidenceDirectory();
const session = `arc-ui-${randomUUID().slice(0, 8)}`;
const defaultWrapper = join(homedir(), ".codex/skills/playwright/scripts/playwright_cli.sh");
const executable = process.env.ARC_PLAYWRIGHT_CLI ?? (existsSync(defaultWrapper) ? defaultWrapper : "npx");
const cliPrefix = executable === "npx" ? ["--yes", "--package", "@playwright/cli@0.1.22", "playwright-cli"] : [];
const steps = [];
const screenshots = [];
const log = join(evidence, "commands.log");
const started = new Date().toISOString();
let caseId = null;
let finalDetail = null;
let outcome = "failed";
let failure = null;
let commands = 0;

function cli(...args) {
  assert(++commands <= 350, "CLI command budget exceeded; stop creating evidence");
  let output;
  try { output = execFileSync(executable, [...cliPrefix, "--session", session, ...args], { cwd: evidence, encoding: "utf8", timeout: 60_000, maxBuffer: 5 * 1024 * 1024 }); }
  catch (error) {
    appendFileSync(log, `${JSON.stringify(args)}\n${error.stdout ?? ""}\n${error.stderr ?? ""}\n`);
    throw new Error(`CLI ${args[0]} failed: ${error.stdout ?? ""} ${error.stderr ?? error.message}`);
  }
  appendFileSync(log, `${JSON.stringify(args)}\n${output}\n`);
  if (output.includes("### Error")) throw new Error(output);
  return output;
}
function record(name, mode = "real-ui", detail = {}) { steps.push({ name, mode, ...detail, at: new Date().toISOString() }); process.stdout.write(`${name}: passed\n`); }
function evaluate(code) {
  const output = cli("eval", code);
  const value = output.match(/### Result\n([\s\S]*?)(?=\n###|$)/)?.[1]?.trim();
  assert(value, "CLI eval did not return an inspectable value");
  try { return JSON.parse(value); } catch { return value; }
}
function snapshot() { return cli("snapshot"); }
function ref(role, name, current = snapshot()) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = current.match(new RegExp(`- ${role} "${escaped}"[^\\n]*\\[ref=([^\\]]+)\\]`));
  assert(match, `${role} ${name} not in the latest snapshot`);
  return match[1];
}
function click(role, name) { cli("click", ref(role, name)); }
function fill(role, name, value) { cli("fill", ref(role, name), value); }
function keyboardButton(name) {
  ref("button", name); // Confirm the control in the latest snapshot first.
  for (let index = 0; index < 30; index++) {
    const current = focus();
    if (current.tag === "BUTTON" && current.text === name) { cli("press", "Enter"); return; }
    cli("press", "Tab");
  }
  throw new Error(`Keyboard could not reach ${name} within 30 Tabs`);
}
function screenshot(name, full = false) {
  assert(screenshots.length < 25, "Screenshot limit reached");
  const path = join(evidence, `${name}.png`);
  try { cli("screenshot", `--filename=${path}`, ...(full ? ["--full-page"] : [])); }
  catch (error) {
    if (!String(error).includes("Timeout")) throw error;
    // The CLI's fixed 5s screenshot timeout can expire during font settling.
    // A bounded CLI diagnostic retry preserves the exact current UI state.
    cli("run-code", `async (page) => { await page.screenshot({path:${JSON.stringify(path)},fullPage:${full},timeout:20000}); }`);
  }
  screenshots.push(path);
}
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function waitSnapshot(test, label, timeout = 180_000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const current = snapshot();
    if (test(current)) return current;
    if (current.includes("文档处理失败")) throw new Error(`${label}: real Intake failed; inspect saved snapshots`);
    await pause(2000);
  }
  throw new Error(`${label}: timed out`);
}
function focus() { return evaluate('() => ({id:document.activeElement?.id,tag:document.activeElement?.tagName,type:document.activeElement?.getAttribute("type"),text:document.activeElement?.textContent,inDialog:!!document.activeElement?.closest("[role=dialog]")})'); }
function layout(dark) {
  const state = evaluate('() => ({theme:document.documentElement.dataset.carbonTheme,width:document.documentElement.scrollWidth,viewport:innerWidth,heading:getComputedStyle(document.querySelector("h1")).color,tile:getComputedStyle(document.querySelector(".cds--tile")).backgroundColor,token:getComputedStyle(document.documentElement).getPropertyValue("--cds-text-primary")})');
  assert(state.width <= state.viewport, `Horizontal page overflow: ${JSON.stringify(state)}`);
  assert.equal(state.theme, dark ? "g100" : "white");
  assert.equal(state.heading, dark ? "rgb(244, 244, 244)" : "rgb(22, 22, 22)");
  assert(state.token.trim(), "Official Carbon theme tokens are missing");
  if (dark) assert.equal(state.tile, "rgb(38, 38, 38)");
  return state;
}
function captureCaseThemes(prefix) {
  if (snapshot().includes('button "切换到浅色模式"')) click("button", "切换到浅色模式");
  for (const width of [1440, 390]) {
    cli("resize", String(width), width === 390 ? "844" : "1000");
    for (const dark of [false, true]) {
      if (dark) click("button", "切换到深色模式");
      record(`${prefix}-${width}-${dark ? "dark" : "light"}`, "real-ui", layout(dark));
      screenshot(`${prefix}-${width}-${dark ? "dark" : "light"}`, true);
    }
    click("button", "切换到浅色模式");
  }
}
function files(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? files(join(root, entry.name)) : [join(root, entry.name)]);
}
async function getDetail() {
  const response = await fetch(new URL(`/api/cases/${encodeURIComponent(caseId)}`, origin), { signal: AbortSignal.timeout(10_000) });
  assert(response.ok, `Read-only verification GET failed: ${response.status}`);
  return response.json();
}

process.stdout.write(`Temporary evidence: ${evidence}\nApproval enabled: ${approve}\n`);
try {
  const version = execFileSync(executable, [...cliPrefix, "--version"], { encoding: "utf8", timeout: 60_000 }).trim();
  record("cli-version", "tool", { version });
  cli("open", origin.href, ...(process.env.ARC_UI_HEADED === "1" ? ["--headed"] : []));
  await waitSnapshot((current) => current.includes('heading "文档风险与决策"'), "dashboard");
  // Start deterministically in light mode, using the actual control.
  if (snapshot().includes('button "切换到浅色模式"')) click("button", "切换到浅色模式");
  for (const width of [1440, 390]) {
    cli("resize", String(width), width === 390 ? "844" : "1000");
    for (const dark of [false, true]) {
      if (dark) click("button", "切换到深色模式");
      record(`dashboard-${width}-${dark ? "dark" : "light"}`, "real-ui", layout(dark));
      screenshot(`dashboard-${width}-${dark ? "dark" : "light"}`, true);
    }
    click("button", "切换到浅色模式");
  }
  // Mobile navigation is entered from the theme button by Tab, Tab, Enter.
  cli("press", "Tab"); assert.equal(focus().text, "总览");
  cli("press", "Tab"); assert.equal(focus().text, "审查队列");
  cli("press", "Enter");
  await waitSnapshot((current) => current.includes('heading "审查队列"'), "queue");
  assert.equal(focus().text, "审查队列");
  record("mobile-keyboard-navigation");
  fill("searchbox", "Filter table", session);
  assert(snapshot().includes('heading "没有匹配案件"'));
  screenshot("queue-empty-390-light"); record("filtered-empty-state");
  fill("searchbox", "Filter table", "");
  click("button", "上传虚构文档");
  assert.equal(focus().id, "upload-title");
  for (let index = 0; index < 7; index++) cli("press", "Tab");
  assert(focus().inDialog, "Upload focus escaped the modal");
  cli("press", "Escape");
  assert.equal(focus().text, "上传虚构文档");
  assert(!snapshot().includes('dialog "本地演示"'));
  record("upload-modal-focus-wrap-and-restore");
  click("button", "总览");
  cli("network-state-set", "offline");
  click("button", "检查状态");
  assert(snapshot().includes("无法加载审查总览"));
  screenshot("dashboard-offline-390-light"); record("offline-error", "browser-network-simulation");
  cli("network-state-set", "online"); click("button", "重试");
  await waitSnapshot((current) => current.includes('heading "文档风险与决策"'), "offline recovery");
  record("network-error-recovery", "browser-network-simulation");
  snapshot(); // Fresh observed action before the necessary intermediate-state capture.
  const loadingPath = join(evidence, "dashboard-loading-390-light.png");
  cli("run-code", `async (page) => { await page.route("**/api/summary", async route => { await new Promise(resolve => setTimeout(resolve, 8000)); await route.continue(); }); await page.getByRole("button", {name:"检查状态"}).click({noWaitAfter:true}); await page.locator(".loading-grid").waitFor({state:"visible",timeout:3000}); await page.screenshot({path:${JSON.stringify(loadingPath)}}); await page.getByRole("heading",{name:"文档风险与决策",exact:true}).waitFor({state:"visible",timeout:15000}); await page.unroute("**/api/summary"); }`);
  screenshots.push(loadingPath);
  await waitSnapshot((current) => current.includes('heading "文档风险与决策"'), "loading recovery");
  record("loading-skeleton", "browser-delay-simulation");
  if (!intake) { outcome = "ui-passed-intake-skipped"; }
  else {
    click("button", "审查队列");
    cli("press", "Tab"); assert.equal(focus().text, "上传虚构文档"); cli("press", "Enter");
    assert.equal(focus().id, "upload-title");
    screenshot("upload-modal-keyboard-390-light");
    const title = `虚构 CLI 审查 ${session}`;
    const input = join(evidence, "synthetic-intake.txt");
    writeFileSync(input, `SYNTHETIC DEMO DOCUMENT\n仅含虚构数据。\n唯一验收标识：${session}\n虚构合同允许无限责任并允许跨境传输。\n虚构邮箱 synthetic-${session}@example.net。\n`, "utf8");
    // Carbon's keyboard-visible chooser button precedes the title field.
    cli("press", "Shift+Tab"); assert.equal(focus().text, "选择文档"); assert(focus().inDialog);
    cli("press", "Enter"); cli("upload", input);
    fill("textbox", "案件标题", title);
    const before = snapshot();
    assert(before.split("\n").find((line) => line.includes('button "提交审查"'))?.includes("[disabled]"));
    cli("press", "Tab"); assert.equal(focus().id, "synthetic-confirmation"); cli("press", "Space");
    assert(snapshot().split("\n").find((line) => line.includes('checkbox "我确认该文档'))?.includes("[checked]"));
    keyboardButton("提交审查");
    await waitSnapshot((current) => current.includes(`heading "${title}"`), "accepted upload");
    const location = evaluate("() => location.href");
    caseId = decodeURIComponent(new URL(location).hash.slice("#case/".length));
    assert(caseId.startsWith("RC-"), "Accepted upload did not navigate to a stable case URL");
    record("real-synthetic-upload", "real-workflow", { case_id: caseId });
    await waitSnapshot((current) => /button "记录决定"[^\n]*\[ref=[^\]]+\](?![^\n]*\[disabled\])/.test(current), "real Intake");
    const reviewed = await getDetail();
    assert.equal(reviewed.source_kind, "uploaded_demo"); assert.equal(reviewed.status, "pending_approval");
    assert(reviewed.assessment_id && reviewed.current_document_version_id && reviewed.source?.langflow_job_id);
    assert.equal(reviewed.source?.hash_kind, "source_bytes_sha256");
    assert.equal(reviewed.source.source_sha256, createHash("sha256").update(readFileSync(input)).digest("hex"));
    captureCaseThemes("intake-completed");
    cli("reload"); await waitSnapshot((current) => current.includes(`heading "${title}"`), "case refresh");
    record("real-intake-and-stable-refresh", "real-workflow", { assessment_id: reviewed.assessment_id, document_version_id: reviewed.current_document_version_id, langflow_job_id: reviewed.source.langflow_job_id });
    click("button", "记录决定"); assert.equal(focus().id, "decision-reason");
    fill("textbox", "决定理由", "短理由");
    assert(snapshot().split("\n").find((line) => line.includes('button "确认决定"'))?.includes("[disabled]"));
    cli("press", "Escape"); assert.equal(focus().text, "记录决定"); record("decision-modal-focus-and-minimum-reason");
    if (!approve) { outcome = "ui-and-intake-passed-approval-disabled"; finalDetail = reviewed; }
    else {
      const reason = `已核验全部虚构条款、来源字节指纹与脱敏证据；本次仅验证演示审查链路 ${session}。`;
      keyboardButton("记录决定"); fill("textbox", "决定理由", reason); keyboardButton("确认决定");
      await waitSnapshot((current) => current.includes("三种格式均可下载"), "real three-format reports");
      finalDetail = await getDetail(); assert.equal(finalDetail.decision, "approved");
      assert.equal(finalDetail.reports.filter((report) => report.state === "ready").length, 3);
      record("real-version-bound-decision-and-three-reports", "real-workflow", { snapshot_hash: finalDetail.reports[0].snapshot_hash });
      captureCaseThemes("reports-ready");
      for (const format of ["json", "html", "pdf"]) {
        keyboardButton(`下载 ${format.toUpperCase()}`);
        const download = files(evidence).find((path) => path.endsWith(`${caseId}-report.${format}`));
        assert(download, `CLI did not save the ${format} browser download`);
        const bytes = readFileSync(download);
        const hash = createHash("sha256").update(bytes).digest("hex");
        assert.equal(hash, finalDetail.reports.find((report) => report.format === format).sha256);
        if (format === "pdf") assert(bytes.subarray(0, 5).equals(Buffer.from("%PDF-")));
        else assert(bytes.toString("utf8").includes(reason));
        record(`real-download-${format}`, "real-workflow", { bytes: bytes.length, sha256: hash, file: relative(evidence, download) });
      }
      // These failure branches are intentionally browser-only simulations.
      const pdfPattern = `**/api/cases/${caseId}/report/pdf?*`;
      cli("route", pdfPattern, "--status=409", "--content-type=application/json", `--body=${JSON.stringify({code:"report_integrity_invalid",detail:"Synthetic integrity failure",retryable:false})}`);
      click("button", "下载 PDF"); assert(snapshot().includes("报告字节与登记指纹不一致"));
      assert.equal(new URL(evaluate("() => location.href")).hash, `#case/${caseId}`);
      screenshot("report-integrity-error-390-light"); cli("unroute", pdfPattern);
      record("download-integrity-error-remains-in-page", "browser-response-simulation");
      const simulated = structuredClone(finalDetail);
      simulated.jobs = simulated.jobs.map((job) => job.kind === "report" ? {...job,state:"failed",retry_generation:0,error_code:"report_generation_failed",retryable:true} : job);
      simulated.reports = simulated.reports.map((report) => report.format === "json" ? report : {...report,state:report.format === "html" ? "failed" : "missing",sha256:null,bytes:null});
      const casePattern = `**/api/cases/${caseId}`;
      const retryPattern = `**/api/cases/${caseId}/reports/retry`;
      cli("route", casePattern, "--content-type=application/json", `--body=${JSON.stringify(simulated)}`);
      cli("route", retryPattern, "--status=202", "--content-type=application/json", `--body=${JSON.stringify({...simulated.jobs.find((job)=>job.kind === "report"),state:"queued"})}`);
      click("button", "刷新状态"); assert(snapshot().includes("部分格式可用"));
      click("button", "重试未完成格式");
      const requestLine = cli("requests").split("\n").filter((line) => line.includes(`[POST] ${origin.origin}/api/cases/${caseId}/reports/retry`)).at(-1);
      const requestIndex = requestLine?.match(/^(\d+)\./)?.[1]; assert(requestIndex, "Retry request not observed by CLI");
      const retryBody = cli("request-body", requestIndex);
      assert(retryBody.includes('"html"') && retryBody.includes('"pdf"') && !retryBody.includes('"json"'));
      screenshot("report-partial-retry-390-light");
      cli("unroute", casePattern); cli("unroute", retryPattern); click("button", "刷新状态");
      assert.equal((await getDetail()).decision, "approved");
      record("failed-missing-only-report-retry", "browser-response-simulation", { formats: ["html", "pdf"] });
      outcome = "passed";
    }
  }
} catch (error) { failure = error instanceof Error ? error.message : String(error); process.stderr.write(`${failure}\n`); process.exitCode = 1; }
finally {
  try { cli("network-state-set", "online"); cli("unroute"); cli("close"); } catch { /* Preserve the original result and all temporary evidence. */ }
  const artifacts = files(evidence).map((path) => ({path:relative(evidence,path),bytes:statSync(path).size,sha256:createHash("sha256").update(readFileSync(path)).digest("hex")}));
  const totalBytes = artifacts.reduce((sum, artifact) => sum + artifact.bytes, 0);
  assert(totalBytes < 64 * 1024 * 1024 && artifacts.length < 500, "Temporary evidence exceeded the declared 64 MiB / 500-file limit");
  writeFileSync(join(evidence, "result.json"), JSON.stringify({started,finished:new Date().toISOString(),outcome,failure,base_url:origin.origin,session,approve,intake,case_id:caseId,steps,artifacts,evidence_bytes:totalBytes,cli_commands:commands}, null, 2));
  process.stdout.write(`Result: ${outcome}\nManifest: ${join(evidence,"result.json")}\n`);
}
