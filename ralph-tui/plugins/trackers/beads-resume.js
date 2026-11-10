// Ralph tracker: beads-bv plus the fixes Ralph 0.12.0 lacks for local Beads projects.
// - Unfinished tasks are reopened and retried before other work (bd ready skips in_progress),
//   including tasks left in_progress by an earlier run that ended or crashed.
// - Pending edits do not block startup; autoCommit includes them after a task completes.
// - sync() exports a local JSONL snapshot; it never runs `bd sync`.
// Default prompt: ~/.config/ralph-tui/templates/beads.hbs (Ralph maps ids containing "beads"
// there, and that file wins over a tracker-supplied template).
import { execFileSync } from 'node:child_process';
import { realpathSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ralphBin = realpathSync(execFileSync('which', ['ralph-tui'], { encoding: 'utf8' }).trim());
const { createBeadsBvTracker } = await import(pathToFileURL(join(dirname(ralphBin), 'index.js')).href);

export default function createTracker() {
  const tracker = createBeadsBvTracker();
  tracker.meta = { ...tracker.meta, id: 'beads-resume', name: 'Beads + BV (resume unfinished, local only)' };
  const next = tracker.getNextTask.bind(tracker);
  const run = (cmd, ...args) => execFileSync(cmd, args, { cwd: tracker.workingDir, encoding: 'utf8' }).trim();
  const bd = (...args) => run('bd', ...args);
  let previousId;
  let started = false;

  const actor = () => process.env.BEADS_ACTOR || run('git', 'config', 'user.name');
  // Only unassigned or own claims; never steal another worker's task.
  const isOwnUnfinished = (issue, me) => issue.status === 'in_progress' && (!issue.assignee || issue.assignee === me);
  const reopen = issue =>
    bd('update', issue.id, '--status', 'open', '--if-status', 'in_progress', '--if-assignee', issue.assignee || '');
  // Return the task if bd still considers it ready (blockers, deferral, epic scope).
  const retry = async (id, filter) => {
    const epic = tracker.getEpicId?.();
    const ready = JSON.parse(bd('ready', '--json', '--brief', '--limit', '0', ...(epic ? ['--parent', epic] : [])));
    return ready.some(t => t.id === id) && !filter?.excludeIds?.includes(id) ? tracker.getTask(id) : undefined;
  };

  tracker.getNextTask = async filter => {
    let resumed;
    if (!started) {
      started = true;
      // Ralph resets in_progress tasks only on Ctrl+C/SIGTERM; a run that ends at its
      // iteration limit or crashes leaves them invisible to bd ready.
      const me = actor();
      const stale = JSON.parse(bd('list', '--status', 'in_progress', '--json', '--limit', '0'))
        .filter(issue => isOwnUnfinished(issue, me));
      stale.forEach(reopen);
      let dirty = '';
      try { dirty = run('git', 'status', '--porcelain', '--', '.', ':(exclude).beads', ':(exclude).ralph-tui'); } catch { /* not a Git repo */ }
      if (dirty) {
        // Prefer a sole unfinished task for pending edits; otherwise use normal selection.
        resumed = stale.length === 1 ? await retry(stale[0].id, filter) : undefined;
      }
    } else if (previousId) {
      const [issue] = JSON.parse(bd('show', previousId, '--json'));
      // Retry this run's unfinished task first so its leftover edits are committed with it.
      if (isOwnUnfinished(issue, actor())) { reopen(issue); resumed = await retry(issue.id, filter); }
    }
    const task = resumed ?? await next(filter);
    previousId = task?.id;
    return task;
  };

  tracker.sync = async () => {
    bd('export', '--output', join(tracker.beadsDir, 'issues.jsonl'));
    return { success: true, message: 'Exported local Beads snapshot', syncedAt: new Date().toISOString() };
  };
  return tracker;
}
