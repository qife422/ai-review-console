/** Real isolated LF login/Flow-list acceptance using fresh CLI snapshots. */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, join } from 'node:path';

const base = new URL(process.env.ARC_LF_BASE_URL ?? 'http://localhost:7860');
assert(['localhost', '127.0.0.1'].includes(base.hostname), 'Only the isolated loopback runtime');
const evidence = process.env.ARC_LF_EVIDENCE_DIR;
assert(evidence && isAbsolute(evidence) && !existsSync(evidence));
assert(existsSync(dirname(evidence)), 'Verifier must create the candidate root first');
mkdirSync(evidence);
const cache = mkdtempSync(join(process.env.RUNNER_TEMP ?? tmpdir(), 'arc-lf-cli-'));
const executable = process.env.ARC_PLAYWRIGHT_CLI ?? 'playwright-cli';
const session = `arc-lf-${randomUUID().slice(0, 8)}`;
let calls = 0;
let logBytes = 0;
let outcome = 'failed';
let failure = null;
const steps = [];
function cli(...args) {
  assert(++calls <= 40, 'CLI command cap exceeded');
  const output = execFileSync(executable, ['--session', session, ...args], {
    cwd: cache, encoding: 'utf8', timeout: 30000, maxBuffer: 256 * 1024,
  });
  const record = `${args[0]}\n${output}\n`;
  if (logBytes + Buffer.byteLength(record) <= 96 * 1024) {
    appendFileSync(join(evidence, 'commands.log'), record);
    logBytes += Buffer.byteLength(record);
  }
  assert(!output.includes('### Error'), 'Browser CLI reported an error; inspect commands.log');
  return output;
}
function snapshot() { return cli('snapshot'); }
function ref(role, pattern) {
  const current = snapshot();
  const rows = current.split('\n');
  for (const line of rows) {
    const match = line.match(new RegExp(`- ${role} "([^"]+)"[^\\n]*\\[ref=([^\\]]+)\\]`));
    if (match && pattern.test(match[1])) return match[2];
  }
  throw new Error(`Expected ${role} absent from fresh snapshot`);
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  cli('open', new URL('/login', base).href);
  for (let index = 0; index < 10; index++) {
    if (/textbox.*(?:Username|User name)/i.test(snapshot())) break;
    await pause(1000);
  }
  cli('fill', ref('textbox', /^(?:Username|User name)(?:\s*\*)?$/i), 'review-admin');
  cli('fill', ref('textbox', /^Password(?:\s*\*)?$/i), 'synthetic-demo-change-me');
  cli('click', ref('button', /^(?:Log in|Login|Sign in)$/i));
  let visible = false;
  for (let index = 0; index < 10; index++) {
    const current = snapshot();
    if (current.includes('Document Review Intake') && current.includes('Document Review Decision')) {
      visible = true;
      writeFileSync(join(evidence, 'flows-visible.txt'), current.slice(0, 48 * 1024));
      break;
    }
    await pause(1500);
  }
  assert(visible, 'The two actually published Flows were not visible after GUI login');
  steps.push('Actual login form submitted', 'Two published project Flows visible');
  outcome = 'passed';
} catch (error) {
  failure = String(error.message).slice(0, 2000);
  process.exitCode = 1;
} finally {
  try { cli('close'); } catch { /* Retain diagnostics; do not overwrite the initial outcome. */ }
  writeFileSync(join(evidence, 'result.json'), JSON.stringify({
    outcome, failure, steps, calls, base_url: base.href,
    scope: 'Real candidate GUI login and visible Flow list only; editor modification is not tested',
    cli_cache: 'Unselected ephemeral runner cache outside the evidence root; no cleanup performed',
  }, null, 2) + '\n');
}
