import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, readdirSync, realpathSync, renameSync } from 'node:fs';
import { hostname } from 'node:os';
import { resolve } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

const cwd = realpathSync(process.cwd());
const lockFile = '.ralph-tui/ralph.lock';
const sessionFile = '.ralph-tui/session.json';
const json = path => {
  try { return JSON.parse(readFileSync(path, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return undefined; throw error; }
};
const run = (command, ...args) => execFileSync(command, args, { encoding: 'utf8', timeout: 10000 }).trim();

function info(pid) {
  try {
    const stat = readFileSync(`/proc/${pid}/stat`, 'utf8');
    const fields = stat.slice(stat.lastIndexOf(')') + 2).split(' ');
    return fields[0] === 'Z' ? undefined : { pid, parent: Number(fields[1]), start: fields[19] };
  } catch (error) {
    if (['ENOENT', 'ESRCH'].includes(error.code)) return undefined;
    throw error;
  }
}

const alive = proc => info(proc.pid)?.start === proc.start;
function signal(proc, name) {
  if (!alive(proc)) return;
  try { process.kill(proc.pid, name); }
  catch (error) { if (error.code !== 'ESRCH') throw error; }
}

async function takeover() {
  const lock = json(lockFile);
  if (process.argv[2] !== undefined && lock && lock.pid !== Number(process.argv[2])) {
    throw new Error('Refusing takeover: the supervised Ralph no longer owns the lock.');
  }
  if (!lock) return;
  if (!Number.isInteger(lock.pid) || lock.pid <= 1 || lock.hostname !== hostname() || realpathSync(lock.cwd) !== cwd) {
    throw new Error('Refusing takeover: lock does not identify a Ralph session on this host and checkout.');
  }
  const owner = info(lock.pid);
  if (!owner) return;
  const ralph = realpathSync(run('which', 'ralph-tui'));
  const processCwd = realpathSync(`/proc/${lock.pid}/cwd`);
  const args = readFileSync(`/proc/${lock.pid}/cmdline`, 'utf8').split('\0');
  const isRalph = args.some(arg => {
    if (!arg) return false;
    try { return realpathSync(resolve(processCwd, arg)) === ralph; } catch { return false; }
  });
  if (!isRalph || processCwd !== cwd) throw new Error(`Refusing takeover: PID ${lock.pid} is not this checkout's Ralph.`);

  const session = json(sessionFile);
  const actor = process.env.BEADS_ACTOR || run('git', 'config', 'user.name');
  const tasks = (session?.activeTaskIds || []).map(id => JSON.parse(run('bd', 'show', id, '--json'))[0])
    .filter(task => task.status === 'in_progress' && (!task.assignee || task.assignee === actor));
  const tree = new Map([[owner.pid, owner]]);
  const collectChildren = () => {
    const processes = readdirSync('/proc').filter(name => /^\d+$/.test(name)).map(name => info(Number(name))).filter(Boolean);
    let added;
    do {
      added = false;
      for (const proc of processes) {
        if (!tree.has(proc.pid) && tree.has(proc.parent) && alive(tree.get(proc.parent))) {
          tree.set(proc.pid, proc);
          added = true;
        }
      }
    } while (added);
  };
  collectChildren();
  console.log(`Stopping this checkout's Ralph (PID ${owner.pid}) before takeover...`);
  signal(owner, 'SIGTERM');
  const deadline = Date.now() + 30000;
  while (alive(owner) && Date.now() < deadline) {
    collectChildren();
    await sleep(100);
  }
  // Ralph can exit before its agent. Stop captured descendants even after reparenting.
  for (const proc of [...tree.values()].reverse()) signal(proc, 'SIGTERM');
  const childDeadline = Date.now() + 5000;
  while ([...tree.values()].some(alive) && Date.now() < childDeadline) await sleep(100);
  for (const proc of [...tree.values()].reverse()) signal(proc, 'SIGKILL');
  const killDeadline = Date.now() + 5000;
  while ([...tree.values()].some(alive) && Date.now() < killDeadline) await sleep(100);
  if ([...tree.values()].some(alive)) throw new Error('Previous Ralph processes did not stop; refusing overlapping launch.');

  const latestLock = json(lockFile);
  if (latestLock && latestLock.pid !== lock.pid) throw new Error('Another Ralph acquired the lock during takeover; refusing launch.');
  // Graceful shutdown reopens the task. Restore only its own still-open claim so
  // beads-resume can associate pending edits with it; completed/blocked work stays put.
  for (const task of tasks) {
    const [current] = JSON.parse(run('bd', 'show', task.id, '--json'));
    if (current.status === 'open' && (current.assignee || '') === (task.assignee || '')) {
      run('bd', 'update', task.id, '--status', 'in_progress', '--if-status', 'open', '--if-assignee', task.assignee || '');
    }
  }
  console.log('Previous Ralph and child agents stopped; starting replacement.');
}

try {
  await takeover();
  const lock = json(lockFile);
  if (lock && info(lock.pid)) throw new Error('Another Ralph is running; refusing to archive its session.');
  // Start fresh without a prompt or --force. Ralph 0.12.0's run --resume tries
  // to acquire its lock twice; retain the old state for inspection instead.
  const archive = `.ralph-tui/reports/takeover-${Date.now()}-${process.pid}`;
  mkdirSync(archive, { recursive: true });
  for (const file of ['session.json', 'session-meta.json', 'progress.md']) {
    try { renameSync(`.ralph-tui/${file}`, `${archive}/${file}`); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
}
catch (error) { console.error(`Ralph takeover failed: ${error.message}`); process.exitCode = 1; }
