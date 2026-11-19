import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
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
  // Ready epics in Beads order; close-eligible drops the ones whose work is done.
  writeFileSync(join(cwd, 'epics'), 'TreeTutor-7t3\nTreeTutor-vm4\nTreeTutor-sh8\n');
  for (const [epic, n] of Object.entries(work)) writeFileSync(join(cwd, `work-${epic}`), String(n));
  const epicWork = flag => `"${cwd}/work-$(sed -n 's/.*${flag} \\([^ ]*\\).*/\\1/p' <<< "$*")"`;
  const bin = (name, body) => writeFileSync(join(cwd, 'bin', name), `#!/usr/bin/env bash\n${body}\n`, { mode: 0o755 });
  bin('bd', `case "$1" in
    ready) if [[ " $* " == *" --type epic "* ]]; then jq -R . "${cwd}/epics" | jq -s 'map({id: .})'; exit; fi
      jq -n --argjson n "$(cat ${epicWork('--parent')} 2>/dev/null || echo 0)" '[range($n)]' ;;
    list) if [[ " $* " == *" --all "* ]]; then cat "${cwd}/all.json" 2>/dev/null || echo '[]'; exit; fi
      if [[ " $* " == *" --parent "* && $* == *open,in_progress,blocked* ]]; then cat "${cwd}/children.json" 2>/dev/null || echo '[]'; exit; fi
      if [[ " $* " == *" --status closed "* ]]; then cat "${cwd}/closed.json" 2>/dev/null || echo '[]'; exit; fi
      if [[ $* == *closed,blocked* ]]; then jq -n --argjson n "$(cat ${epicWork('--parent')}.done 2>/dev/null || echo 0)" '[range($n)]'; exit; fi
      echo '[]' ;;
    # A made gate is open, so the next check must not make another.
    create) echo "$3" >> "${cwd}/creates"; echo '[{"labels":["gate:backlog"],"status":"open"}]' > "${cwd}/all.json"; echo TreeTutor-gate ;;
    dep) echo "$*" >> "${cwd}/deps" ;;
    show) cat "${cwd}/show-$2.json" ;;
    # Adopting a blocker makes it the epic's one ready task.
    update) echo "$*" >> "${cwd}/updates"; rm -f "${cwd}/children.json"; echo 1 > ${epicWork('--parent')} ;;
    epic) open=(); closed=()
      while read -r e; do if [[ $(cat "${cwd}/work-$e" 2>/dev/null) == 0 ]]; then closed+=("$e"); else open+=("$e"); fi; done < "${cwd}/epics"
      printf '%s\n' "\${open[@]}" | grep . > "${cwd}/epics" || :
      jq -n '{closed: $ARGS.positional}' --args "\${closed[@]}" ;;
    *) echo '[]' ;;
  esac`);
  bin('ralph-tui', `echo "$*" >> "${cwd}/runs"; f=${epicWork('--epic')}
[[ -z $FIXTURE_SLOW ]] || /usr/bin/sleep "$FIXTURE_SLOW"
# FIXTURE_CLOSE: the agent closes a task and leaves an edit; FIXTURE_RALPH_COMMITS: Ralph's auto-commit works.
[[ -z $FIXTURE_CLOSE ]] || { echo edit > work.txt; echo '[{"id":"TreeTutor-7t3.1","issue_type":"task","title":"Fix it"}]' > "${cwd}/closed.json"; }
[[ -z $FIXTURE_RALPH_COMMITS ]] || { git add -A && git commit -q --no-verify -m 'task: by Ralph'; }
[[ -n $FIXTURE_NO_PROGRESS ]] || { echo $(( $(cat "$f") - 1 )) > "$f"; echo $(( $(cat "$f.done" 2>/dev/null) + 1 )) > "$f.done"; }`);
  // Limited until the first wait has passed, like a usage window that resets.
  const agent = name => bin(name, `echo '${name}' >> "${cwd}/probes"
echo "$*" >> "${cwd}/probe-${name}-args"
if [[ $(cat "${cwd}/limited-agent" 2>/dev/null) == '${name}' || ( " $FIXTURE_LIMITED " == *" ${name} "* && ! -e "${cwd}/sleeps" ) ]]; then echo "You've hit your usage limit" >&2; exit 1; fi; echo pong`);
  agent('claude');
  agent('codex');
  bin('sleep', `echo "$1" >> "${cwd}/sleeps"; [[ -z $FIXTURE_WAIT_ENDS_WORK ]] || rm -f "${cwd}"/work-*`);
  bin('date', `if [[ $1 == +%H ]]; then echo "\${FIXTURE_HOUR:-12}"; else exec /usr/bin/date "$@"; fi`);
  const read = name => existsSync(join(cwd, name)) ? readFileSync(join(cwd, name), 'utf8').trim().split('\n') : [];
  const script = fileURLToPath(new URL('../bin/ralph-afk', import.meta.url));
  const options = env => ({ cwd, env: { ...process.env, HOME: cwd, PATH: `${cwd}/bin:${process.env.PATH}`, BEADS_ACTOR: 'fixture', ...env } });
  const run = (env = {}, args = []) => spawnSync('bash', [script, ...args], { ...options(env), encoding: 'utf8', timeout: 20000 });
  const start = (env = {}) => spawn('bash', [script], options(env));
  return { run, start, read, bin, cwd, runs: () => read('runs'), sleeps: () => read('sleeps') };
}

test('a limited Claude hands the task to Codex, which keeps the next task after Claude resets', () => {
  const f = fixture({ 'TreeTutor-7t3': 2 });
  const result = f.run({ FIXTURE_LIMITED: 'claude', RALPH_AFK_WAIT: '7' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  // One task per run, and no switch back to Claude while Codex still answers.
  const codex = 'run --headless --epic TreeTutor-7t3 --iterations 1 --agent codex --model gpt-6.2-sol';
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

test('an agent missing from the table never launches', () => {
  const unknown = fixture();
  const result = unknown.run({ RALPH_AFK_SCHEDULE: '00-24=nobody', FIXTURE_WAIT_ENDS_WORK: '1' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stderr, /Unknown agent in RALPH_AFK_SCHEDULE: nobody/);
  assert.deepEqual(unknown.runs(), []);
});

test('-a limits the run to those agents; typos and unscheduled agents are refused at start', () => {
  const f = fixture({ 'TreeTutor-sh8': 1 });
  const result = f.run({}, ['-a', 'codex', 'TreeTutor-sh8']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.runs(), ['run --headless --epic TreeTutor-sh8 --iterations 1 --agent codex --model gpt-6.2-sol']);
  assert.ok(!f.read('probes').includes('claude'));

  const unscheduled = fixture();
  const refused = unscheduled.run({ RALPH_AFK_SCHEDULE: '00-24=claude' }, ['-a', 'claude,codex']);
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /codex is in no RALPH_AFK_SCHEDULE window/);
  assert.deepEqual(unscheduled.runs(), []);

  const typo = fixture();
  const unknown = typo.run({}, ['-a', 'codx']);
  assert.equal(unknown.status, 2);
  assert.match(unknown.stderr, /Unknown agent: codx/);
  assert.deepEqual(typo.runs(), []);
});

test('when an epic runs out of work it closes and the next ready epic starts', () => {
  const f = fixture({ 'TreeTutor-7t3': 1, 'TreeTutor-sh8': 1 });
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.runs().map(run => run.split(' ')[3]), ['TreeTutor-7t3', 'TreeTutor-sh8']);
  assert.match(result.stdout, /Closed finished epics: TreeTutor-7t3\n/);
  assert.match(result.stdout, /Closed finished epics: TreeTutor-sh8\n/);
});

test('epics nobody ordered are not chained: a later ready epic runs while an earlier one has no work', () => {
  const f = fixture({ 'TreeTutor-vm4': 1 });
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.read('deps'), []);
  assert.deepEqual(f.runs().map(run => run.split(' ')[3]), ['TreeTutor-vm4']);
});

test('a parentless blocker of an epic task moves under the epic and runs; one in another epic does not', () => {
  const f = fixture({ 'TreeTutor-7t3': 0 });
  const blocks = id => ({ type: 'blocks', depends_on_id: id });
  writeFileSync(join(f.cwd, 'children.json'), JSON.stringify([{ id: 'TreeTutor-7t3.2', dependencies: [blocks('TreeTutor-7t3.1'), blocks('TreeTutor-bug'), blocks('TreeTutor-other')] }]));
  writeFileSync(join(f.cwd, 'show-TreeTutor-bug.json'), JSON.stringify([{ parent: null, status: 'open', issue_type: 'bug' }]));
  writeFileSync(join(f.cwd, 'show-TreeTutor-other.json'), JSON.stringify([{ parent: 'TreeTutor-vm4', status: 'open', issue_type: 'bug' }]));
  const result = f.run({}, ['TreeTutor-7t3']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.read('updates'), ['update TreeTutor-bug --parent TreeTutor-7t3']);
  assert.match(result.stdout, /Moved TreeTutor-bug under TreeTutor-7t3/);
  assert.deepEqual(f.runs(), ['run --headless --epic TreeTutor-7t3 --iterations 1 --agent claude --model opus']);
});

test('ralph with no epic takes the first ready epic from Beads', () => {
  const f = fixture();
  const ralph = fileURLToPath(new URL('../bin/ralph', import.meta.url));
  const result = spawnSync('bash', [ralph, '--iterations', '1'], {
    cwd: f.cwd, encoding: 'utf8', env: { ...process.env, HOME: f.cwd, PATH: `${f.cwd}/bin:${process.env.PATH}` },
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(f.runs(), ['run --headless --epic TreeTutor-7t3 --iterations 1']);
});

test('a task that finishes fast starts the next one without waiting', () => {
  const f = fixture({ 'TreeTutor-7t3': 2 });
  const result = f.run();
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.runs().length, 2);
  assert.deepEqual(f.sleeps(), []);
});

test('a short run that finishes nothing waits before the next try', () => {
  const f = fixture();
  const result = f.run({ FIXTURE_NO_PROGRESS: '1', FIXTURE_WAIT_ENDS_WORK: '1' });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.equal(f.runs().length, 1);
  assert.deepEqual(f.sleeps(), ['600']);
  assert.match(result.stdout, /without finishing a task/);
});

test('Ctrl+C lets the running task finish, then stops', async () => {
  const f = fixture({ 'TreeTutor-7t3': 2 });
  const child = f.start({ FIXTURE_SLOW: '1' });
  let stdout = '';
  child.stdout.on('data', data => { stdout += data; });
  await new Promise(resolve => setTimeout(resolve, 500));
  child.kill('SIGINT');
  const status = await new Promise(resolve => child.on('exit', resolve));
  assert.equal(status, 0, stdout);
  assert.match(stdout, /Stop requested/);
  assert.equal(f.runs().length, 1);
  assert.equal(f.read('work-TreeTutor-7t3')[0], '1', 'The running task must finish');
});

test('a finished task Ralph left uncommitted is committed, even past a failing hook', () => {
  for (const ralphCommits of [false, true]) {
    const f = fixture();
    execFileSync('git', ['-C', f.cwd, 'config', 'core.hooksPath', join(f.cwd, 'hooks')]);
    mkdirSync(join(f.cwd, 'hooks'));
    writeFileSync(join(f.cwd, 'hooks/pre-commit'), '#!/bin/sh\nexit 1\n', { mode: 0o755 });
    const git = { GIT_AUTHOR_NAME: 'fixture', GIT_AUTHOR_EMAIL: 'f@example.invalid', GIT_COMMITTER_NAME: 'fixture', GIT_COMMITTER_EMAIL: 'f@example.invalid' };
    const result = f.run({ ...git, FIXTURE_CLOSE: '1', ...(ralphCommits && { FIXTURE_RALPH_COMMITS: '1' }) });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const log = execFileSync('git', ['-C', f.cwd, 'log', '--format=%s'], { encoding: 'utf8' }).trim();
    assert.equal(log, ralphCommits ? 'task: by Ralph' : 'task: TreeTutor-7t3.1 Fix it');
    assert.equal(execFileSync('git', ['-C', f.cwd, 'status', '--porcelain', '--', 'work.txt'], { encoding: 'utf8' }), '', 'The task edit must be committed');
  }
});

test('out of ready work, a gate epic is made once, only if a task closed after the last gate', () => {
  const gate = { labels: ['gate:backlog'], status: 'closed', closed_at: '2026-01-02' };
  const task = closed_at => ({ issue_type: 'task', status: 'closed', closed_at });
  for (const [all, made] of [[[gate, task('2026-01-03')], true], [[task('2026-01-01'), gate], false], [[], false]]) {
    const f = fixture({ 'TreeTutor-7t3': 0 });
    writeFileSync(join(f.cwd, 'all.json'), JSON.stringify(all));
    const result = f.run();
    assert.equal(result.status, 0, result.stdout + result.stderr);
    assert.equal(f.read('creates').length, made ? 2 : 0, JSON.stringify(all));
    assert.match(result.stdout, /No ready work/);
  }
});
