import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { once } from 'node:events';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { hostname, tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

async function waitFor(check) {
  for (let n = 0; n < 100; n++) {
    if (check()) return;
    await sleep(50);
  }
  assert.fail('Timed out waiting for fixture');
}

const script = name => fileURLToPath(new URL(`../bin/${name}`, import.meta.url));

function fixture(t) {
  const cwd = mkdtempSync(join(tmpdir(), 'ralph-takeover-'));
  // The scripts work on the Git checkout they are called from.
  execFileSync('git', ['init', '-q', cwd]);
  for (const dir of ['.ralph-tui', 'bin', '.config/ralph-tui/plugins/trackers']) mkdirSync(join(cwd, dir), { recursive: true });
  const env = { ...process.env, HOME: cwd, PATH: `${cwd}/bin:${process.env.PATH}`, BEADS_ACTOR: 'fixture', RALPH_CODEX_MODEL: 'fixture-model' };
  writeFileSync(join(cwd, '.config/ralph-tui/plugins/trackers/beads-resume.js'), '');
  writeFileSync(join(cwd, '.ralph-tui/epics'), '# fixture order\nTreeTutor-7t3\nTreeTutor-vm4\n');
  writeFileSync(join(cwd, 'issue.json'), JSON.stringify({ id: 'task-1', status: 'in_progress', assignee: 'fixture' }));
  writeFileSync(join(cwd, 'bin/bd'), `#!${process.execPath}
const fs = require('node:fs');
const issue = JSON.parse(fs.readFileSync('issue.json'));
const args = process.argv.slice(2);
if (args[0] === 'show') console.log(JSON.stringify([issue]));
else if (args[0] === 'update' && args.includes('--if-status') && args.includes('--if-assignee')) {
  if (issue.status !== args[args.indexOf('--if-status') + 1] || issue.assignee !== args[args.indexOf('--if-assignee') + 1]) process.exit(1);
  issue.status = args[args.indexOf('--status') + 1];
  fs.writeFileSync('issue.json', JSON.stringify(issue));
} else process.exit(90);
`, { mode: 0o755 });
  writeFileSync(join(cwd, 'bin/ralph-tui'), `#!${process.execPath}
const fs = require('node:fs');
const { spawn } = require('node:child_process');
if (process.argv.includes('--fixture-running')) {
  setInterval(() => {}, 1000);
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  fs.writeFileSync('.ralph-tui/session.json', JSON.stringify({ sessionId: 'fixture', activeTaskIds: ['task-1'] }));
  fs.writeFileSync('.ralph-tui/ralph.lock', JSON.stringify({ pid: process.pid, cwd: process.cwd(), hostname: require('node:os').hostname() }));
  fs.writeFileSync('child.pid', String(child.pid));
  process.on('SIGTERM', () => {
    if (process.env.FIXTURE_IGNORE_TERM) return;
    const issue = JSON.parse(fs.readFileSync('issue.json'));
    issue.status = process.env.FIXTURE_FINAL_STATUS || 'open';
    if (process.env.FIXTURE_NEXT_OWNER) issue.assignee = process.env.FIXTURE_NEXT_OWNER;
    fs.writeFileSync('issue.json', JSON.stringify(issue));
    fs.writeFileSync('.ralph-tui/session.json', JSON.stringify({ sessionId: 'fixture', activeTaskIds: [] }));
    fs.writeFileSync('stopped', 'yes');
    // Leave an orphan child to ensure takeover waits for the whole old tree.
    process.exit(0);
  });
} else fs.writeFileSync('started.json', JSON.stringify({ args: process.argv.slice(2), issue: JSON.parse(fs.readFileSync('issue.json')) }));
`, { mode: 0o755 });
  const run = async (...args) => {
    const p = spawn('bash', [script(args.shift()), ...args], { cwd, env });
    let output = '';
    p.stdout.on('data', data => { output += data; });
    p.stderr.on('data', data => { output += data; });
    const [code] = await once(p, 'exit');
    return { code, output };
  };
  const start = async (extraEnv = {}) => {
    const p = spawn(join(cwd, 'bin/ralph-tui'), ['--fixture-running'], { cwd, env: { ...env, ...extraEnv }, stdio: 'ignore' });
    t.after(() => { p.kill('SIGKILL'); });
    await waitFor(() => existsSync(join(cwd, 'child.pid')));
    const child = Number(readFileSync(join(cwd, 'child.pid'), 'utf8'));
    t.after(() => { try { process.kill(child, 'SIGKILL'); } catch {} });
    return { p, child };
  };
  return { cwd, env, run, start, started: () => JSON.parse(readFileSync(join(cwd, 'started.json'))) };
}

test('scheduled takeover stops the old Ralph and orphan agent before launching Claude', async t => {
  const f = fixture(t);
  const { p, child } = await f.start();
  const result = await f.run('ralph', '--takeover');
  assert.equal(result.code, 0, result.output);
  assert.notEqual(p.exitCode, null);
  const stat = existsSync(`/proc/${child}/stat`) ? readFileSync(`/proc/${child}/stat`, 'utf8').split(') ')[1][0] : null;
  assert.ok(stat === null || stat === 'Z', 'Child agent must have stopped');
  assert.ok(existsSync(join(f.cwd, 'stopped')));
  assert.equal(f.started().issue.status, 'in_progress', 'Resume pending edits after Ralph reopens the interrupted issue');
  assert.ok(!f.started().args.includes('--takeover'));
  assert.ok(!f.started().args.includes('--resume'));
  assert.ok(!existsSync(join(f.cwd, '.ralph-tui/session.json')), 'Archive session to avoid an interactive startup prompt');
  const archive = readdirSync(join(f.cwd, '.ralph-tui/reports'))[0];
  assert.ok(existsSync(join(f.cwd, '.ralph-tui/reports', archive, 'session.json')));
});

test('a named agent gets its model: RALPH_<NAME>_MODEL, else the agents table, unless --model is given', async t => {
  const f = fixture(t);
  const result = await f.run('ralph', '--takeover', '--agent', 'codex', '--iterations', '3');
  assert.equal(result.code, 0, result.output);
  assert.deepEqual(f.started().args, ['run', '--headless', '--epic', 'TreeTutor-7t3', '--agent', 'codex', '--iterations', '3', '--model', 'fixture-model']);
  await f.run('ralph', '--agent', 'claude');
  assert.deepEqual(f.started().args.slice(-2), ['--model', 'opus']);
  await f.run('ralph', '--agent', 'codex', '--model', 'mine');
  assert.deepEqual(f.started().args.slice(-4), ['--agent', 'codex', '--model', 'mine']);
});

test('stale locks do not prevent an unattended takeover', async t => {
  const f = fixture(t);
  writeFileSync(join(f.cwd, '.ralph-tui/ralph.lock'), JSON.stringify({ pid: 2147483647, cwd: f.cwd, hostname: hostname() }));
  const result = await f.run('ralph', 'other-epic', '--takeover');
  assert.equal(result.code, 0, result.output);
  assert.ok(f.started().args.includes('other-epic'));
});

test('a lock pointing to an unrelated process is refused without starting or killing it', async t => {
  const f = fixture(t);
  writeFileSync(join(f.cwd, '.ralph-tui/ralph.lock'), JSON.stringify({ pid: process.pid, cwd: f.cwd, hostname: hostname() }));
  const result = await f.run('ralph', '--takeover');
  assert.notEqual(result.code, 0);
  assert.ok(!existsSync(join(f.cwd, 'started.json')));
});

test('a supervisor cannot stop a replacement Ralph that acquired the lock', async t => {
  const f = fixture(t);
  const { p } = await f.start();
  const helper = spawn(process.execPath, [script('ralph-takeover.mjs'), String(process.pid)], { cwd: f.cwd, env: f.env });
  let output = '';
  helper.stderr.on('data', data => { output += data; });
  const [code] = await once(helper, 'exit');
  assert.notEqual(code, 0);
  assert.match(output, /supervised Ralph no longer owns the lock/);
  assert.equal(p.exitCode, null);
  assert.ok(!existsSync(join(f.cwd, 'stopped')));
});

test('takeover preserves a task completed during shutdown', async t => {
  const f = fixture(t);
  await f.start({ FIXTURE_FINAL_STATUS: 'closed' });
  const result = await f.run('ralph', '--takeover');
  assert.equal(result.code, 0, result.output);
  assert.equal(f.started().issue.status, 'closed');
});

test('ordinary launches keep existing arguments', async t => {
  const f = fixture(t);
  const result = await f.run('ralph', 'other-epic', '--iterations', '7');
  assert.equal(result.code, 0, result.output);
  assert.deepEqual(f.started().args, ['run', '--headless', '--epic', 'other-epic', '--iterations', '7']);
});

test('shutdown ownership changes are preserved', async t => {
  const f = fixture(t);
  await f.start({ FIXTURE_NEXT_OWNER: 'another-worker' });
  const result = await f.run('ralph', '--takeover');
  assert.equal(result.code, 0, result.output);
  assert.equal(f.started().issue.status, 'open');
  assert.equal(f.started().issue.assignee, 'another-worker');
});

test('help and an unsafe force combination do not stop a running session', async t => {
  const f = fixture(t);
  const { p } = await f.start();
  assert.equal((await f.run('ralph', '--takeover', '--help')).code, 0);
  assert.equal(p.exitCode, null);
  assert.notEqual((await f.run('ralph', '--takeover', '--force')).code, 0);
  assert.equal(p.exitCode, null);
});

test('a hung Ralph is killed automatically before replacement starts', { timeout: 45000 }, async t => {
  const f = fixture(t);
  const { p } = await f.start({ FIXTURE_IGNORE_TERM: '1' });
  const result = await f.run('ralph', '--takeover', '--agent', 'codex');
  assert.equal(result.code, 0, result.output);
  assert.equal(p.signalCode, 'SIGKILL');
  assert.ok(!existsSync(join(f.cwd, '.ralph-tui/session.json')));
  assert.equal(f.started().issue.status, 'in_progress');
});
