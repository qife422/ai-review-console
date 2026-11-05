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
const editor = process.env.ARC_LF_VERIFY_EDITOR === '1';
const statePath = join(evidence, 'editor-state.json');
let editorEvidence = null;
let calls = 0;
let logBytes = 0;
let outcome = 'failed';
let failure = null;
const steps = [];
function cli(...args) {
  assert(++calls <= (editor ? 100 : 40), 'CLI command cap exceeded');
  const output = execFileSync(executable, ['--session', session, ...args], {
    cwd: cache, encoding: 'utf8', timeout: 30000, maxBuffer: 256 * 1024,
  });
  const record = `${args[0]}\n${output}\n`;
  if (logBytes + Buffer.byteLength(record) <= (editor ? 80 : 96) * 1024) {
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
      writeFileSync(join(evidence, 'flows-visible.txt'), current.slice(0, editor ? 16 * 1024 : 48 * 1024));
      break;
    }
    await pause(1500);
  }
  assert(visible, 'The two actually published Flows were not visible after GUI login');
  steps.push('Actual login form submitted', 'Two published project Flows visible');
  if (editor) {
    const python = process.env.ARC_LF_PYTHON ?? '.venv/bin/python';
    const helper = (action) => JSON.parse(execFileSync(python, [
      'scripts/prepare_langflow_editor.py', action, '--state', statePath,
    ], { encoding: 'utf8', timeout: 60000, maxBuffer: 128 * 1024 }));
    const state = helper('prepare');
    // The API only creates the isolated copy; all subsequent edits use visible UI controls.
    cli('reload');
    let ready = false;
    for (let index = 0; index < 10; index++) {
      if (snapshot().includes(`Open flow ${state.original_name}`)) { ready = true; break; }
      await pause(1000);
    }
    assert(ready, 'Synthetic Flow is not visible on the list');
    cli('click', ref('button', new RegExp(`^Open flow ${state.original_name}$`)));
    let editorSnapshot = '';
    for (let index = 0; index < 10; index++) {
      editorSnapshot = snapshot();
      if (editorSnapshot.includes(state.original_name) && !editorSnapshot.includes('Open flow ' + state.original_name)) break;
      await pause(1000);
    }
    writeFileSync(join(evidence, 'editor-visible.txt'), editorSnapshot.slice(0, 16 * 1024));
    const shape = cli('eval', `() => 'ARC_SHAPE:' + document.querySelectorAll('.react-flow__node').length + ':' + document.querySelectorAll('.react-flow__edge').length`);
    const parsed = shape.match(/ARC_SHAPE:(\d+):(\d+)/);
    assert(parsed && Number(parsed[1]) > 0 && Number(parsed[2]) > 0, 'Editor nodes and edges not observed');
    cli('screenshot', `--filename=${join(evidence, 'editor.png')}`);
    // Resolve each actionable reference against a fresh snapshot. Unsupported UI fails closed.
    const renameButton = ref('button', new RegExp(`^${state.original_name}$`));
    cli('click', renameButton);
    const nameField = ref('textbox', /^(?:Flow name|Name)$/i);
    cli('fill', nameField, state.edited_name);
    cli('click', ref('button', /^(?:Save|Save changes)$/i));
    let saved = false;
    for (let index = 0; index < 10; index++) {
      if (snapshot().includes('Changes saved successfully')) { saved = true; break; }
      await pause(1000);
    }
    assert(saved, 'Flow settings saved toast was not observed');
    cli('reload');
    let persisted = false;
    for (let index = 0; index < 10; index++) {
      if (snapshot().includes(state.edited_name)) { persisted = true; break; }
      await pause(1000);
    }
    assert(persisted, 'Edited name not visible after reload');
    editorEvidence = helper('verify');
    steps.push('Synthetic copy opened in editor', 'Visible UI renamed synthetic Flow',
      'Reload and API confirmed persisted name', 'Original Flow IDs and graph hashes unchanged');
  }
  outcome = 'passed';
} catch (error) {
  failure = String(error.message).slice(0, 2000);
  if (editor) { try { writeFileSync(join(evidence, 'failure-snapshot.txt'), snapshot().slice(0, 16 * 1024)); } catch { /* Preserve original failure. */ } }
  process.exitCode = 1;
} finally {
  try { cli('close'); } catch { /* Retain diagnostics; do not overwrite the initial outcome. */ }
  writeFileSync(join(evidence, 'result.json'), JSON.stringify({
    outcome, failure, steps, calls, base_url: base.href, editor_evidence: editorEvidence,
    scope: editor ? 'Synthetic copy editor only; custom code editing, business Flow changes and production are not tested' : 'Real candidate GUI login and visible Flow list only; editor modification is not tested',
    cli_cache: 'Unselected ephemeral runner cache outside the evidence root; no cleanup performed',
  }, null, 2) + '\n');
}
