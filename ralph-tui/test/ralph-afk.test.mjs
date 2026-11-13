import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Fake CLIs only: no model calls. `work` holds the number of ready issues per epic; each Ralph run finishes one.
function fixture(work = { 'TreeTutor-7t3': 1 }) {
  const cwd = mkdtempSync(join(tmpdir(), 'ralph-afk-'));
  // The scripts work on the Git checkout they are called from.
  execFileSync('git', ['init', '-q', cwd]);
  for (const dir of ['.ralph-tui', 'bin', '.config/ralph-tui/plugins/trackers']) mkdirSync(join(cwd, dir), { recursive: true });
  writeFileSync(join(cwd, '.config/ralph-tui/plugins/trackers/beads-resume.js'), '');
  writeFileSync(join(cwd, '.ralph-tui/epics'), '# fixture order\nTreeTutor-7t3\n\nTreeTutor-vm4\nTreeTutor-sh8\n');
  for (const [epic, n] of Object.entries(work)) writeFileSync(join(cwd, `work-${epic}`), String(n));
  const epicWork = flag => `"${cwd}/work-$(sed -n 's/.*${flag} \\([^ ]*\\).*/\\1/p' <<< "$*")"`;
  const bin = (name, body) => writeFileSync(join(cwd, 'bin', name), `#!/usr/bin/env bash\n${body}\n`, { mode: 0o755 });
  bin('bd', `case "$1" in
    ready) jq -n --argjson n "$(cat ${epicWork('--parent')} 2>/dev/null || echo 0)" '[range($n)]' ;;
    show) cat "${cwd}/issue.json" ;;
    update) echo '[{"id":"task-1","status":"in_progress","assignee":"fixture"}]' > "${cwd}/issue.json" ;;
    *) echo '[]' ;;
  esac`);
  bin('ralph-tui', `if [[ -n $FIXTURE_RUNNING ]]; then exec "${process.execPath}" "${cwd}/running.cjs" "$0" "$@"; fi
echo "$*" >> "${cwd}/runs"; f=${epicWork('--epic')}; echo $(( $(cat "$f") - 1 )) > "$f"`);
  writeFileSync(join(cwd, 'running.cjs'), `
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const args = process.argv.slice(3);
const agent = args[args.indexOf('--agent') + 1];
const work = 'work-' + args[args.indexOf('--epic') + 1];
fs.appendFileSync('runs', args.join(' ') + '\\n');
if (fs.existsSync('partial.txt')) {
  require('node:assert/strict').equal(JSON.parse(fs.readFileSync('issue.json'))[0].status, 'in_progress');
  require('node:assert/strict').equal(fs.readFileSync('partial.txt', 'utf8'), 'unfinished edit');
  fs.writeFileSync('resumed', 'yes');
  fs.writeFileSync(work, String(Number(fs.readFileSync(work)) - 1));
} else {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  fs.writeFileSync('child.pid', String(child.pid));
  fs.writeFileSync('partial.txt', 'unfinished edit');
  fs.writeFileSync('issue.json', JSON.stringify([{ id: 'task-1', status: 'in_progress', assignee: 'fixture' }]));
  fs.writeFileSync('.ralph-tui/ralph.lock', JSON.stringify({ pid: process.pid, cwd: process.cwd(), hostname: require('node:os').hostname() }));
  fs.writeFileSync('.ralph-tui/session.json', JSON.stringify({ activeTaskIds: ['task-1'] }));
  process.on('SIGTERM', () => {
    fs.writeFileSync('issue.json', JSON.stringify([{ id: 'task-1', status: 'open', assignee: 'fixture' }]));
    fs.writeFileSync('stopped', 'yes');
    process.exit(0);
  });
  console.log('Working on usage limit handling; ordinary task output must not trigger a handoff.');
  if (process.env.FIXTURE_RUNNING !== 'healthy') fs.writeFileSync('limited-agent', agent);
  // A provider that lets the running session finish: new requests fail, the task keeps printing.
  if (process.env.FIXTURE_RUNNING === 'busy') setInterval(() => console.log('still working'), 20);
  setTimeout(() => {
    child.kill();
    if (['healthy', 'busy'].includes(process.env.FIXTURE_RUNNING)) fs.writeFileSync(work, String(Number(fs.readFileSync(work)) - 1));
    else fs.writeFileSync('timed-out', 'yes');
    process.exit(0);
  }, process.env.FIXTURE_RUNNING === 'healthy' ? 300 : 1500);
}
`);
  // Limited until the first wait has passed, like a usage window that resets.
  const agent = name => bin(name, `echo '${name}' >> "${cwd}/probes"
echo "$*" >> "${cwd}/probe-${name}-args"
if [[ $(cat "${cwd}/limited-agent" 2>/dev/null) == '${name}' || ( " $FIXTURE_LIMITED " == *" ${name} "* && ! -e "${cwd}/sleeps" ) ]]; then echo "You've hit your usage limit" >&2; exit 1; fi; echo pong`);
  agent('claude');
  agent('codex');
  bin('sleep', `if [[ ! -e /proc/$$/fd/9 ]]; then echo "$1" >> "${cwd}/checks"; exec /usr/bin/sleep 0.05; fi
echo "$1" >> "${cwd}/sleeps"; [[ -z $FIXTURE_WAIT_ENDS_WORK ]] || rm -f "${cwd}"/work-*`);
  bin('date', `if [[ $1 == +%H ]]; then echo "\${FIXTURE_HOUR:-12}"; else exec /usr/bin/date "$@"; fi`);
  const read = name => existsSync(join(cwd, name)) ? readFileSync(join(cwd, name), 'utf8').trim().split('\n') : [];
  const run = (env = {}, args = []) => spawnSync('bash', [fileURLToPath(new URL('../bin/ralph-afk', import.meta.url)), ...args], {
    cwd, encoding: 'utf8', timeout: 20000,
    env: { ...process.env, HOME: cwd, PATH: `${cwd}/bin:${process.env.PATH}`, BEADS_ACTOR: 'fixture', ...env },
  });
  return { run, read, bin, cwd, runs: () => read('runs'), sleeps: () => read('sleeps') };
}

test('a limited Claude hands the task to Codex, which keeps the next task after Claude resets', () => {
  const f = fixture({ 'TreeTutor-7t3': 2 });
  const result = f.run({ FIXTURE_LIMITED: 'claude', RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  // The second cycle follows a wait, by which time the fixture's Claude limit has reset:
  // one task per run, and no switch back while Codex still answers.
  const codex = 'run --headless --epic TreeTutor-7t3 --iterations 1 --agent codex --model gpt-6.1-sol';
  assert.deepEqual(f.runs(), [codex, codex]);
  assert.match(result.stdout, /No ready work/);
});

test('with every agent limited it waits, then starts once usage is back', () => {
  const f = fixture();
  const result = f.run({ FIXTURE_LIMITED: 'claude codex', RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.sleeps()[0], '7');
  assert.equal(f.runs().length, 1);
  assert.match(f.runs()[0], /--agent claude/);
});

test('the schedule picks the agent for the hour and runs nothing outside its windows', () => {
  const schedule = { RALPH_AFK_SCHEDULE: '00-06=codex 08-24=claude,codex' };
  const night = fixture();
  assert.equal(night.run({ ...schedule, FIXTURE_HOUR: '03' }).status, 0);
  assert.match(night.runs()[0], /--agent codex/);

  // 07:00 has no window: it must wait rather than launch.
  const gap = fixture();
  assert.equal(gap.run({ ...schedule, FIXTURE_HOUR: '07', FIXTURE_WAIT_ENDS_WORK: '1' }).status, 0);
  assert.deepEqual(gap.runs(), []);
  assert.equal(gap.sleeps().length, 1);
});

test('any agent in the table runs with its own probe and model; an unknown one never launches', () => {
  const cursor = fixture();
  cursor.bin('agent', 'echo pong');
  assert.equal(cursor.run({ RALPH_AFK_SCHEDULE: '00-24=cursor' }).status, 0);
  assert.deepEqual(cursor.runs(), ['run --headless --epic TreeTutor-7t3 --iterations 1 --agent cursor --model auto']);

  const unknown = fixture();
  const result = unknown.run({ RALPH_AFK_SCHEDULE: '00-24=nobody', FIXTURE_WAIT_ENDS_WORK: '1' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stderr, /Unknown agent in RALPH_AFK_SCHEDULE: nobody/);
  assert.deepEqual(unknown.runs(), []);
});

test('agent names among the arguments limit the run to those agents; the rest are epics', () => {
  const f = fixture({ 'TreeTutor-sh8': 1 });
  const result = f.run({}, ['codex', 'TreeTutor-sh8']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.runs(), ['run --headless --epic TreeTutor-sh8 --iterations 1 --agent codex --model gpt-6.1-sol']);
  assert.ok(!f.read('probes').includes('claude'));

  const unscheduled = fixture();
  const refused = unscheduled.run({ RALPH_AFK_SCHEDULE: '00-24=claude' }, ['codex']);
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /codex is in no RALPH_AFK_SCHEDULE window/);
  assert.deepEqual(unscheduled.runs(), []);
});

test('when an epic runs out of work it moves to the next one that has some', () => {
  const f = fixture({ 'TreeTutor-7t3': 1, 'TreeTutor-sh8': 1 });
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.runs().map(run => run.split(' ')[3]), ['TreeTutor-7t3', 'TreeTutor-sh8']);
});

for (const agent of ['claude', 'codex']) test(`a ${agent} limit mid-task stops Ralph and its agent, then resumes pending edits on the other provider`, () => {
  const f = fixture();
  const result = f.run({ FIXTURE_RUNNING: 'limited', RALPH_AFK_SCHEDULE: `00-24=${agent},${agent === 'claude' ? 'codex' : 'claude'}`, RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.read('stopped'), ['yes'], 'Supervisor must stop the stalled run instead of waiting for it to end');
  assert.deepEqual(f.read('timed-out'), []);
  assert.deepEqual(f.read('resumed'), ['yes']);
  assert.deepEqual(f.sleeps(), ['7'], 'Mid-task interruption must skip the short-run delay before fallback');
  assert.equal(f.runs().length, 2);
  assert.match(f.runs()[0], new RegExp(`--agent ${agent}`));
  assert.match(f.runs()[1], new RegExp(`--agent ${agent === 'claude' ? 'codex' : 'claude'}`));
  assert.ok(f.read('probe-claude-args').every(args => args.includes('--model haiku')));
  assert.ok(f.read('probe-codex-args').every(args => args.includes('-m gpt-6-luna')));
  assert.ok(f.read('probe-claude-args').every(args => args.includes('--effort low')));
  assert.ok(f.read('probe-codex-args').every(args => args.includes('-c model_reasoning_effort="low"')));
  assert.ok(f.read('checks').every(seconds => seconds === '7'));
  const child = f.read('child.pid')[0];
  assert.ok(!existsSync(`/proc/${child}/stat`) || readFileSync(`/proc/${child}/stat`, 'utf8').split(') ')[1][0] === 'Z');
});

test('a healthy task keeps running even when its output mentions usage limits', () => {
  const f = fixture();
  const result = f.run({ FIXTURE_RUNNING: 'healthy' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.runs().length, 1);
  assert.deepEqual(f.read('stopped'), []);
  assert.ok(f.read('probes').length > 1, 'Healthy provider must remain available during mid-task probes');
  assert.ok(f.read('checks').every(seconds => seconds === '600'), 'Checks default to ten minutes');
});

test('a limit mid-task does not stop a run that is still producing output', () => {
  const f = fixture();
  const result = f.run({ FIXTURE_RUNNING: 'busy', RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /still producing output/);
  assert.deepEqual(f.read('stopped'), []);
  assert.equal(f.runs().length, 1);
  assert.match(result.stdout, /No ready work/);
});

test('a failed stop keeps the supervisor alive and is retried at the next check', () => {
  const f = fixture();
  const bd = join(f.cwd, 'bin/bd');
  writeFileSync(bd, readFileSync(bd, 'utf8').replace('\n', `\nif [[ $1 == show && ! -e "${f.cwd}/show-failed" ]]; then touch "${f.cwd}/show-failed"; exit 1; fi\n`));
  const result = f.run({ FIXTURE_RUNNING: 'limited', RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /Could not stop Ralph/);
  assert.deepEqual(f.read('resumed'), ['yes']);
  assert.deepEqual(f.runs().map(run => /--agent (\S+)/.exec(run)[1]), ['claude', 'codex']);
});
