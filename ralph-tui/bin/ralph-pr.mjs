// ralph-afk --pr [workers]: parallel PR mode. Each worker takes one ready task into its own worktree and
// branch, opens a PR and waits for CI; one reviewer at a time reviews, fixes and squash-merges green PRs.
// ralph-afk holds the checkout lock and starts this from the repository root. See docs/ralph.md.
import { execFileSync, spawn } from 'node:child_process';
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, readdirSync, symlinkSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as sleep } from 'node:timers/promises';

const here = dirname(fileURLToPath(import.meta.url));
const root = process.cwd();
const { env } = process;
const slots = Number(process.argv[2] ?? env.RALPH_PR_WORKERS ?? 3);
const schedule = env.RALPH_AFK_SCHEDULE ?? '00-24=claude,codex';
const waitMs = Number(env.RALPH_AFK_WAIT ?? 600) * 1000;
const pollMs = Number(env.RALPH_PR_POLL ?? 120) * 1000;
const SLOW_EVERY = 5; // merges between slow-suite runs on GitHub
const TRIES = 3; // failed agent runs on one task or PR before it needs a human
const trees = join(dirname(root), `${basename(root)}-pr`); // outside the checkout, so nothing lands in .gitignore
const logs = join(root, '.ralph-tui/pr-logs');
const prompts = { worker: '.ralph-tui/pr-worker.md', reviewer: '.ralph-tui/pr-reviewer.md' };

const log = message => console.log(`[ralph-pr ${new Date().toLocaleString('sv')}] ${message}`);
const run = (command, args, options = {}) =>
  execFileSync(command, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...options }).trim();
const attempt = (command, args, options) => {
  try { return run(command, args, options); } catch { return null; }
};
const json = (command, args) => JSON.parse(run(command, args) || 'null');
const fail = message => { console.error(message); process.exit(1); };
const labelled = (issue, ...names) => (issue.labels ?? []).some(label => names.includes(label));
const show = id => { const out = attempt('bd', ['show', id, '--json']); return out && JSON.parse(out)[0]; };

if (!Number.isInteger(slots) || slots < 1) fail('Usage: ralph-afk --pr [workers]; workers is a whole number from 1.');
for (const [stage, file] of Object.entries(prompts)) {
  if (!existsSync(file)) fail(`Missing ${file}: the ${stage} prompt for ralph-afk --pr.`);
}
const table = readFileSync(join(here, '../agents'), 'utf8').split('\n')
  .filter(line => line.trim() && !line.trimStart().startsWith('#'))
  .map(line => { const [stage, agent, model, effort, ...probe] = line.split('|'); return { stage, agent, model, effort, probe: probe.join('|') }; });
for (const stage of Object.keys(prompts)) {
  const rows = table.filter(row => row.stage === stage);
  if (!rows.length) fail(`No ${stage} line in ${join(here, '../agents')}.`);
  for (const row of rows) if (!['claude', 'codex'].includes(row.agent)) fail(`ralph-afk --pr runs claude and codex only, not ${row.agent}.`);
}

// Same windows as ralph-afk: space-separated FROM-TO=agents in local hours.
function scheduled() {
  const hour = new Date().getHours();
  for (const window of schedule.split(/\s+/).filter(Boolean)) {
    const [hours, list] = window.split('=');
    const [from, to] = hours.split('-').map(Number);
    if (hour >= from && hour < to) return list.split(',');
  }
  return [];
}
const probed = new Map(); // agent -> { ok, until }
function usable(row) {
  const known = probed.get(row.agent);
  if (known && known.until > Date.now()) return known.ok;
  const reply = attempt('bash', ['-c', row.probe], { cwd: '/tmp', timeout: 180000 }) ?? '';
  const ok = reply.toLowerCase().includes('pong');
  probed.set(row.agent, { ok, until: Date.now() + waitMs });
  if (!ok) log(`${row.agent} is not usable now (usage limit, auth or network).`);
  return ok;
}
// The first usable agent of the stage in table order. The reviewer has one line, so it only waits.
const pick = stage => table.find(row => row.stage === stage && scheduled().includes(row.agent) && usable(row));
const down = agent => probed.set(agent, { ok: false, until: Date.now() + waitMs });

const commonGit = run('git', ['rev-parse', '--path-format=absolute', '--git-common-dir']);
function command(row, prompt) {
  const effort = row.effort && row.effort !== '-' ? row.effort : null;
  if (row.agent === 'claude') {
    return ['claude', ['-p', '--permission-mode', 'auto', '--model', row.model, ...(effort ? ['--effort', effort] : []), prompt]];
  }
  // Commits and bd writes land in the main checkout's .git and .beads, outside the worktree sandbox.
  const roots = JSON.stringify([commonGit, join(root, '.beads')]);
  return ['codex', ['exec', '--approve-for-me', '-m', row.model, ...(effort ? ['-c', `model_reasoning_effort="${effort}"`] : []),
    '-c', `sandbox_workspace_write.writable_roots=${roots}`, '-c', 'sandbox_workspace_write.network_access=true', prompt]];
}
const running = new Set();
function launch(row, stage, name, cwd, facts) {
  const prompt = `${readFileSync(prompts[stage], 'utf8')}\n\n## This run\n\n${facts.join('\n')}\n`;
  const [bin, args] = command(row, prompt);
  const out = openSync(join(logs, `${name}.log`), 'a');
  // detached: Ctrl+C in this terminal reaches only the supervisor, never a running agent.
  const child = spawn(bin, args, { cwd, stdio: ['ignore', out, out], detached: true });
  closeSync(out);
  const job = { stage, name, agent: row.agent, started: Date.now(), child, ...Object.fromEntries(facts.map(fact => [fact.slice(0, fact.indexOf(': ')), fact.slice(fact.indexOf(': ') + 2)])) };
  job.done = new Promise(resolve => {
    child.on('exit', code => resolve((job.code = code ?? 1)));
    child.on('error', error => { log(`Could not start ${bin}: ${error.message}`); resolve((job.code = 127)); });
  });
  running.add(job);
  log(`Started ${row.agent} ${row.model} as ${stage} for ${name}; log: .ralph-tui/pr-logs/${name}.log`);
  return job;
}

const tries = new Map();
// A task or PR that keeps failing waits for the owner instead of spinning.
function failed(id, what) {
  const n = (tries.get(id) ?? 0) + 1;
  tries.set(id, n);
  if (n < TRIES) return;
  attempt('bd', ['update', id, '--add-label', 'needs-human']);
  attempt('bd', ['note', id, `ralph-afk --pr: ${what} failed ${n} times; see .ralph-tui/pr-logs/.`]);
  log(`${id} failed ${n} times; labelled needs-human.`);
}

const base = json('gh', ['repo', 'view', '--json', 'defaultBranchRef']).defaultBranchRef.name;
const reviewTree = join(trees, 'reviewer');
mkdirSync(logs, { recursive: true });
mkdirSync(trees, { recursive: true });
// The owner's planning commits must reach GitHub before workers branch from it.
try { run('git', ['push', '-q', 'origin', base], { stdio: ['ignore', 'pipe', 'inherit'] }); }
catch { fail(`Could not push local ${base} to origin; fix that first (diverged, or the pre-push secret scan refused).`); }
run('git', ['fetch', '-q', 'origin']);
if (!existsSync(reviewTree)) run('git', ['worktree', 'add', '-q', '--detach', reviewTree, `origin/${base}`]);
// A previous run stopped mid-task: give its unfinished claims back.
for (const id of readdirSync(trees).filter(name => name !== 'reviewer')) {
  const task = show(id);
  if (task?.status === 'in_progress' && !labelled(task, 'in-review')) attempt('bd', ['unclaim', id]);
}

const reminded = new Set();
function readyTasks() {
  const epics = new Map(json('bd', ['ready', '--type', 'epic', '--sort', 'oldest', '--json', '--limit', '0'])
    .filter(epic => !labelled(epic, 'gate:backlog')).map((epic, index) => [epic.id, index]));
  // Parentless tasks (fixes filed mid-run) first, then by epic age; bd's own order within an epic.
  return json('bd', ['ready', '--json', '--limit', '0'])
    .filter(task => task.issue_type !== 'epic' && !labelled(task, 'gate:backlog', 'in-review', 'needs-human'))
    .filter(task => !task.parent || epics.has(task.parent))
    .filter(task => {
      if (!labelled(task, 'new-ui') || /^Mockup:\s*\S/m.test(task.description ?? '')) return true;
      if (!reminded.has(task.id)) log(`Skipping ${task.id}: a new-ui ticket needs a "Mockup:" line linking docs/mockups/${task.id}.html or .png.`);
      reminded.add(task.id);
      return false;
    })
    .sort((a, b) => (epics.get(a.parent) ?? -1) - (epics.get(b.parent) ?? -1));
}
// Agents read code and run single test files, so a worktree borrows the main checkout's dependencies.
function borrowModules(path) {
  if (existsSync(join(root, 'node_modules')) && !existsSync(join(path, 'node_modules'))) symlinkSync(join(root, 'node_modules'), join(path, 'node_modules'));
}
function startWorker(task, row) {
  if (attempt('bd', ['update', task.id, '--claim']) === null) return;
  const path = join(trees, task.id);
  try {
    if (!existsSync(path)) {
      run('git', ['fetch', '-q', 'origin']);
      const branch = attempt('git', ['rev-parse', '-q', '--verify', `refs/heads/${task.id}`]);
      run('git', ['worktree', 'add', '-q', ...(branch ? [path, task.id] : ['-b', task.id, path, `origin/${base}`])]);
    }
    borrowModules(path);
  } catch (error) {
    log(`Could not make the worktree for ${task.id}: ${error.stderr || error.message}`);
    attempt('bd', ['unclaim', task.id]);
    return failed(task.id, 'making the worktree');
  }
  launch(row, 'worker', task.id, path, [`Task: ${task.id}`, `Title: ${task.title}`, `Branch: ${task.id}`, `Base: ${base}`]);
}
function workerDone(job) {
  const task = show(job.Task);
  if (task && (task.status === 'closed' || labelled(task, 'in-review'))) return log(`${job.Task}: PR in review.`);
  if (task && labelled(task, 'needs-human')) {
    attempt('bd', ['unclaim', job.Task]);
    return log(`${job.Task} needs a human; other work continues.`);
  }
  log(`${job.Task}: ${job.agent} exited with ${job.code} before the PR was in review; the task is ready again.`);
  if (Date.now() - job.started < 120000) down(job.agent);
  attempt('bd', ['unclaim', job.Task]);
  failed(job.Task, 'the worker');
}

// Open PRs whose branch is a Beads task still open here, oldest first.
function taskPrs() {
  return json('gh', ['pr', 'list', '--state', 'open', '--limit', '100', '--json', 'number,headRefName,title,statusCheckRollup'])
    .map(pr => ({ ...pr, task: show(pr.headRefName) }))
    .filter(pr => pr.task && pr.task.status !== 'closed')
    .sort((a, b) => a.number - b.number);
}
const settled = pr => pr.statusCheckRollup?.length &&
  pr.statusCheckRollup.every(check => (check.status ?? 'COMPLETED') === 'COMPLETED' && !['PENDING', 'EXPECTED'].includes(check.state));
function startReview(pr, row) {
  // Each review starts from a clean, current base; the reviewer checks the PR out detached.
  run('git', ['fetch', '-q', 'origin']);
  run('git', ['checkout', '-q', '-f', '--detach', `origin/${base}`], { cwd: reviewTree });
  run('git', ['clean', '-fdq'], { cwd: reviewTree });
  borrowModules(reviewTree);
  launch(row, 'reviewer', `review-${pr.number}`, reviewTree,
    [`PR: #${pr.number}`, `Task: ${pr.task.id}`, `Title: ${pr.task.title}`, `Branch: ${pr.headRefName}`, `Base: ${base}`]);
}
let merges = 0;
let slow = null; // the dispatched slow-suite run being watched
function reviewDone(job) {
  const number = job.PR.slice(1);
  const state = JSON.parse(attempt('gh', ['pr', 'view', number, '--json', 'state']) ?? '{}').state;
  if (state !== 'MERGED') {
    if (labelled(show(job.Task) ?? {}, 'needs-human')) return log(`PR ${job.PR} needs a human; skipping it until the label is gone.`);
    log(`PR ${job.PR}: ${job.agent} exited with ${job.code} without merging.`);
    if (Date.now() - job.started < 120000) down(job.agent);
    return failed(job.Task, 'the review');
  }
  attempt('bd', ['close', job.Task, '--reason', `Merged in PR ${job.PR}`]);
  const path = join(trees, job.Task);
  if (existsSync(path)) attempt('git', ['worktree', 'remove', '--force', path]);
  attempt('git', ['branch', '-D', job.Task]);
  attempt('git', ['push', '-q', 'origin', '--delete', job.Task]); // GitHub keeps merged branches unless asked
  log(`Merged PR ${job.PR} (${job.Task}).`);
  pull();
  if (++merges % SLOW_EVERY === 0) dispatchSlow();
}
// The owner's checkout follows GitHub only while it has nothing of its own; the Beads export does not count.
function pull() {
  const branch = run('git', ['rev-parse', '--abbrev-ref', 'HEAD']);
  const changes = run('git', ['status', '--porcelain', '--untracked-files=no']).split('\n')
    .filter(line => line && !line.endsWith(' .beads/issues.jsonl'));
  if (branch !== base || changes.length) return log(`Not pulling the main checkout: it is on ${branch} or has local changes.`);
  if (attempt('git', ['pull', '-q', '--ff-only', 'origin', base]) === null) log(`Could not fast-forward the main checkout to origin/${base}.`);
}
function dispatchSlow() {
  const since = new Date(Date.now() - 60000).toISOString(); // a minute of clock skew
  if (attempt('gh', ['workflow', 'run', 'slow-tests.yml', '--ref', base]) === null) return log('Could not start the slow-test workflow.');
  slow = { since, until: Date.now() + 3600000 };
  log(`${merges} merges: started the slow-test workflow.`);
}
function checkSlow() {
  if (!slow) return;
  const runs = json('gh', ['run', 'list', '--workflow', 'slow-tests.yml', '--event', 'workflow_dispatch', '--limit', '1', '--json', 'status,conclusion,url,createdAt']);
  const latest = runs.find(entry => entry.createdAt >= slow.since);
  if (!latest || latest.status !== 'completed') {
    if (Date.now() > slow.until) { log('The slow-test workflow did not finish within an hour; no longer waiting.'); slow = null; }
    return;
  }
  slow = null;
  if (latest.conclusion === 'success') return log('The slow-test workflow passed.');
  const id = createTask('Fix test:slow failures', `The slow-test workflow failed on ${base}: ${latest.url}. Reproduce from the run log, fix every failure and open a PR.`);
  log(`The slow-test workflow failed (${latest.url}); filed ${id ?? 'nothing: bd create failed'}.`);
}
// Same as ralph-afk: bd cannot change a database's prefix, so honour config.yaml's issue-prefix with an explicit ID.
function createTask(title, description) {
  const config = existsSync('.beads/config.yaml') ? readFileSync('.beads/config.yaml', 'utf8') : '';
  const prefix = /^issue-prefix: *"?([^"\n]*)"? *$/m.exec(config)?.[1];
  let id = [];
  if (prefix) {
    let candidate;
    do candidate = `${prefix}-${Math.random().toString(36).slice(2, 5)}`; while (show(candidate));
    id = ['--force', '--id', candidate];
  }
  return attempt('bd', ['create', ...id, '--type', 'task', '--title', title, '--description', description, '--silent']);
}

let stopping = false;
const stopAll = () => { for (const job of running) try { process.kill(-job.child.pid, 'SIGTERM'); } catch {} };
process.on('SIGINT', () => {
  if (stopping) { stopAll(); process.exit(130); }
  stopping = true;
  log('Stopping after the running agents finish. Press Ctrl+C again to stop now.');
});
process.on('SIGTERM', () => { stopAll(); process.exit(143); });

log(`PR mode on ${base}: up to ${slots} workers, one reviewer.`);
for (;;) {
  const closed = JSON.parse(attempt('bd', ['epic', 'close-eligible', '--json']) ?? '{}').closed ?? [];
  if (closed.length) log(`Closed finished epics: ${closed.join(' ')}`);
  checkSlow();
  const workers = [...running].filter(job => job.stage === 'worker');
  const ready = stopping ? [] : readyTasks().filter(task => !workers.some(job => job.Task === task.id));
  for (const task of ready.slice(0, slots - workers.length)) {
    const row = pick('worker');
    if (!row) { log('No worker agent available now.'); break; }
    startWorker(task, row);
  }
  const prs = taskPrs().filter(pr => !labelled(pr.task, 'needs-human'));
  const reviewing = [...running].some(job => job.stage === 'reviewer');
  const next = prs.find(pr => labelled(pr.task, 'in-review') && settled(pr));
  if (!stopping && !reviewing && next) {
    const row = pick('reviewer');
    if (row) startReview(next, row);
    else log('The reviewer agent is not available now; waiting.');
  }
  if (!running.size && (stopping || (!ready.length && !prs.length && !slow))) break;
  await Promise.race([sleep(pollMs), ...[...running].map(job => job.done)]);
  for (const job of running) {
    if (job.code === undefined) continue;
    running.delete(job);
    (job.stage === 'worker' ? workerDone : reviewDone)(job);
  }
}

if (stopping) log('Stop requested. Stopping.');
else log('No ready tasks and no open PRs left. Stopping.');
// Workers never commit the Beads export; commit it once here so the next start pushes it with the planning commits.
if (run('git', ['rev-parse', '--abbrev-ref', 'HEAD']) === base && run('git', ['status', '--porcelain', '--', '.beads/issues.jsonl'])) {
  if (attempt('git', ['commit', '-q', '-m', 'chore(beads): export after ralph-afk --pr', '--', '.beads/issues.jsonl']) !== null) log('Committed the Beads export.');
}
const parked = json('bd', ['list', '--label', 'needs-human', '--status', 'open,in_progress,blocked', '--json', '--limit', '0']) ?? [];
if (parked.length) {
  console.log('Waiting for a human:');
  for (const task of parked) console.log(`  ${task.id} ${task.title}`);
}
