import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Real Git with a bare origin; fake bd, gh and agents (no model calls). Agents finish their job at once:
// a worker commits, pushes, opens a PR and labels the task in-review; the reviewer merges the PR.
const fakeBd = `const fs = require('fs');
const file = process.env.FIX + '/issues.json';
const issues = JSON.parse(fs.readFileSync(file, 'utf8'));
const save = () => fs.writeFileSync(file, JSON.stringify(issues));
const [cmd, ...rest] = process.argv.slice(2);
const flag = name => { const i = rest.indexOf(name); return i < 0 ? undefined : rest[i + 1]; };
const get = id => issues.find(issue => issue.id === id);
const out = value => console.log(JSON.stringify(value));
fs.appendFileSync(process.env.FIX + '/bd-calls', [cmd, ...rest].join(' ') + '\\n');
switch (cmd) {
  case 'ready': {
    const ready = issues.filter(i => i.status === 'open' && (!flag('--type') || i.issue_type === flag('--type')));
    if (flag('--sort') === 'oldest') ready.sort((a, b) => (a.created_at ?? '').localeCompare(b.created_at ?? ''));
    out(ready); break;
  }
  case 'show': if (!get(rest[0])) process.exit(1); out([get(rest[0])]); break;
  case 'update': {
    const issue = get(rest[0]);
    if (rest.includes('--claim')) { if (issue.status !== 'open') process.exit(1); issue.status = 'in_progress'; }
    if (flag('--add-label')) issue.labels.push(flag('--add-label'));
    save(); break;
  }
  case 'unclaim': get(rest[0]).status = 'open'; save(); break;
  case 'close': get(rest[0]).status = 'closed'; save(); break;
  case 'create': {
    const id = flag('--id') ?? 'T-new';
    issues.push({ id, title: flag('--title'), issue_type: flag('--type'), status: 'open', labels: [], description: flag('--description') });
    save(); console.log(id); break;
  }
  case 'list': out(issues.filter(i => i.status !== 'closed' && i.labels.includes(flag('--label')))); break;
  case 'epic': out({ closed: [] }); break;
  default: out([]);
}`;
const fakeGh = `const fs = require('fs');
const read = (name, fallback) => fs.existsSync(process.env.FIX + '/' + name) ? JSON.parse(fs.readFileSync(process.env.FIX + '/' + name, 'utf8')) : fallback;
const write = (name, value) => fs.writeFileSync(process.env.FIX + '/' + name, JSON.stringify(value));
const args = process.argv.slice(2);
const flag = name => args[args.indexOf(name) + 1];
const out = value => console.log(JSON.stringify(value));
const prs = read('prs.json', []);
switch (args.slice(0, 2).join(' ')) {
  case 'repo view': out({ defaultBranchRef: { name: 'master' } }); break;
  case 'pr create':
    prs.push({ number: prs.length + 1, headRefName: flag('--head'), title: flag('--title'), state: 'OPEN', statusCheckRollup: [{ status: 'COMPLETED', conclusion: 'SUCCESS' }] });
    write('prs.json', prs); break;
  case 'pr list': out(prs.filter(pr => pr.state === 'OPEN')); break;
  case 'pr view': out({ state: prs[args[2] - 1].state }); break;
  case 'pr merge': prs[args[2] - 1].state = 'MERGED'; write('prs.json', prs); fs.appendFileSync(process.env.FIX + '/merges', args[2] + '\\n'); break;
  case 'workflow run':
    fs.appendFileSync(process.env.FIX + '/dispatches', args.join(' ') + '\\n');
    write('runs.json', [{ status: 'completed', conclusion: process.env.FIXTURE_SLOW || 'success', url: 'https://example.invalid/run/1', createdAt: new Date().toISOString() }]);
    break;
  case 'run list': out(read('runs.json', [])); break;
}`;
const agent = name => `#!/usr/bin/env bash
prompt="\${@: -1}"
if [[ $* == *'Reply with exactly: pong'* && $* != *'## This run'* ]]; then
  # FIXTURE_LIMITED: out of usage until another agent has run.
  [[ " $FIXTURE_LIMITED " != *" ${name} "* || -e "$FIX/agents" ]] || exit 1
  echo pong; exit
fi
task=$(sed -n 's/^Task: //p' <<< "$prompt")
echo "${name} $task \${*:1:$#-1}" >> "$FIX/agents"
if [[ $prompt == *'PR: #'* ]]; then
  [[ ! -e "$FIX/reviewing" ]] || echo overlap >> "$FIX/overlap"
  touch "$FIX/reviewing"; /usr/bin/sleep 0.2
  gh pr merge "$(sed -n 's/^PR: #//p' <<< "$prompt")" --squash
  rm "$FIX/reviewing"; exit
fi
[[ " $FIXTURE_FAIL " != *" $task "* ]] || exit 1
echo "$task" > "$task.txt" && git add "$task.txt" && git commit -qm "$task" && git push -q origin "$task"
gh pr create --head "$task" --title "$task"
bd update "$task" --add-label in-review`;

const identity = { GIT_AUTHOR_NAME: 'fixture', GIT_AUTHOR_EMAIL: 'f@example.invalid', GIT_COMMITTER_NAME: 'fixture', GIT_COMMITTER_EMAIL: 'f@example.invalid' };
const epic = (id, created_at) => ({ id, title: id, issue_type: 'epic', status: 'open', labels: [], created_at });
const task = (id, parent, extra = {}) => ({ id, title: `Do ${id}`, issue_type: 'task', status: 'open', labels: [], parent, ...extra });

function fixture(issues) {
  const base = mkdtempSync(join(tmpdir(), 'ralph-pr-'));
  const cwd = join(base, 'repo');
  const fix = join(base, 'fix');
  const git = (...args) => execFileSync('git', args, { cwd, env: { ...process.env, ...identity } });
  execFileSync('git', ['init', '-q', '--bare', '-b', 'master', join(base, 'origin.git')]);
  mkdirSync(cwd);
  git('init', '-q', '-b', 'master');
  writeFileSync(join(cwd, 'README'), 'fixture\n');
  git('add', 'README');
  git('commit', '-qm', 'start');
  git('remote', 'add', 'origin', join(base, 'origin.git'));
  git('push', '-q', '-u', 'origin', 'master');
  for (const dir of [join(cwd, '.ralph-tui'), join(fix, 'bin')]) mkdirSync(dir, { recursive: true });
  writeFileSync(join(cwd, '.ralph-tui/pr-worker.md'), '# Worker prompt\n');
  writeFileSync(join(cwd, '.ralph-tui/pr-reviewer.md'), '# Reviewer prompt\n');
  writeFileSync(join(fix, 'issues.json'), JSON.stringify(issues));
  const bin = (name, body) => writeFileSync(join(fix, 'bin', name), body, { mode: 0o755 });
  writeFileSync(join(fix, 'bd.cjs'), fakeBd);
  writeFileSync(join(fix, 'gh.cjs'), fakeGh);
  // flock: agents and the supervisor write the fake state at the same time.
  bin('bd', `#!/bin/sh\nexec flock "$FIX/lock" node "$FIX/bd.cjs" "$@"\n`);
  bin('gh', `#!/bin/sh\nexec flock "$FIX/lock" node "$FIX/gh.cjs" "$@"\n`);
  bin('claude', agent('claude'));
  bin('codex', agent('codex'));
  const read = name => existsSync(join(fix, name)) ? readFileSync(join(fix, name), 'utf8').trim().split('\n') : [];
  const script = fileURLToPath(new URL('../bin/ralph-afk', import.meta.url));
  const options = env => ({
    cwd, env: { ...process.env, ...identity, FIX: fix, PATH: `${fix}/bin:${process.env.PATH}`, RALPH_PR_POLL: '0.05', RALPH_AFK_WAIT: '0', ...env },
  });
  const run = (env = {}, args = []) => spawnSync('bash', [script, '--pr', ...args], { ...options(env), encoding: 'utf8', timeout: 30000 });
  const issue = id => JSON.parse(readFileSync(join(fix, 'issues.json'), 'utf8')).find(i => i.id === id);
  return { base, cwd, run, read, issue, claims: () => read('bd-calls').filter(call => call.endsWith('--claim')) };
}

test('workers open one PR per task, oldest epic first; one reviewer at a time merges them and cleans up', () => {
  const f = fixture([epic('E2', '2026-01-02'), task('E2.1', 'E2'), epic('E1', '2026-01-01'), task('E1.1', 'E1'), task('E1.2', 'E1')]);
  const result = f.run({}, ['2']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.claims(), ['update E1.1 --claim', 'update E1.2 --claim', 'update E2.1 --claim']);
  assert.deepEqual(f.read('merges'), ['1', '2', '3']);
  assert.deepEqual(f.read('overlap'), []);
  for (const id of ['E1.1', 'E1.2', 'E2.1']) {
    assert.equal(f.issue(id).status, 'closed', id);
    assert.ok(!existsSync(join(f.base, 'repo-pr', id)), `${id} worktree removed`);
  }
  assert.equal(execFileSync('git', ['branch', '--all', '--list', '*E*'], { cwd: f.cwd, encoding: 'utf8' }), '');
  assert.equal(execFileSync('git', ['ls-remote', '--heads', 'origin'], { cwd: f.cwd, encoding: 'utf8' }).match(/refs\/heads\/E/g), null);
  const agents = f.read('agents');
  assert.ok(agents.filter(line => / E\d\.\d -p --permission-mode auto --model sonnet --effort high$/.test(line)).length === 3, agents.join('\n'));
  // The fake reviewer reads the task line too, so match the reviewer's model instead.
  assert.equal(agents.filter(line => line.endsWith('-p --permission-mode auto --model opus --effort high')).length, 3, agents.join('\n'));
  assert.match(result.stdout, /No ready tasks and no open PRs left/);
});

test('--pr refuses to start without the worker prompt', () => {
  const f = fixture([epic('E1'), task('E1.1', 'E1')]);
  rmSync(join(f.cwd, '.ralph-tui/pr-worker.md'));
  const result = f.run();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Missing \.ralph-tui\/pr-worker\.md/);
  assert.deepEqual(f.claims(), []);
});

test('a new-ui ticket without a Mockup line is skipped with a reminder; one with a mockup runs', () => {
  const f = fixture([epic('E1'), task('E1.1', 'E1', { labels: ['new-ui'], description: 'A new panel.' }),
    task('E1.2', 'E1', { labels: ['new-ui'], description: 'A new panel.\nMockup: docs/mockups/E1.2.html' })]);
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /Skipping E1\.1: a new-ui ticket needs a "Mockup:" line/);
  assert.deepEqual(f.claims(), ['update E1.2 --claim']);
  assert.equal(f.issue('E1.1').status, 'open');
  assert.equal(f.issue('E1.2').status, 'closed');
});

test('with Claude out of usage a Codex worker takes the task; the reviewer waits for Claude', () => {
  const f = fixture([epic('E1'), task('E1.1', 'E1')]);
  const result = f.run({ FIXTURE_LIMITED: 'claude' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const [worker, reviewer, ...rest] = f.read('agents');
  assert.match(worker, /^codex E1\.1 exec --approve-for-me -m gpt-6\.2-sol -c model_reasoning_effort="medium" -c sandbox_workspace_write\.writable_roots=\[.*\] -c sandbox_workspace_write\.network_access=true$/);
  assert.match(reviewer, /^claude E1\.1 -p --permission-mode auto --model opus/);
  assert.deepEqual(rest, []);
});

test('a task whose worker keeps failing gets needs-human after 3 tries while other work merges', () => {
  const f = fixture([epic('E1'), task('E1.1', 'E1'), task('E1.2', 'E1')]);
  const result = f.run({ FIXTURE_FAIL: 'E1.1' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.claims().filter(call => call.includes('E1.1')).length, 3);
  assert.ok(f.issue('E1.1').labels.includes('needs-human'));
  assert.equal(f.issue('E1.2').status, 'closed');
  assert.match(result.stdout, /Waiting for a human:\n {2}E1\.1 Do E1\.1/);
});

test('every 5 merges the slow suite runs on GitHub; a failure files a fix task that a worker takes', () => {
  const f = fixture([epic('E1'), ...[1, 2, 3, 4, 5].map(n => task(`E1.${n}`, 'E1'))]);
  const result = f.run({ FIXTURE_SLOW: 'failure' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.read('dispatches'), ['workflow run slow-tests.yml --ref master']);
  assert.equal(f.issue('T-new').title, 'Fix test:slow failures');
  assert.match(f.issue('T-new').description, /https:\/\/example\.invalid\/run\/1/);
  assert.equal(f.issue('T-new').status, 'closed');
  assert.equal(f.read('merges').length, 6);
});

test('--pr shares the sequential lock: a second supervisor in the checkout is refused', async () => {
  const f = fixture([epic('E1'), task('E1.1', 'E1')]);
  const holder = spawn('flock', [join(f.cwd, '.ralph-tui/afk.lock'), 'sleep', '5']);
  await new Promise(resolve => setTimeout(resolve, 200));
  try {
    const result = f.run();
    assert.equal(result.status, 1);
    assert.match(result.stderr, /already running in this checkout/);
    assert.deepEqual(f.claims(), []);
  } finally { holder.kill(); }
});
