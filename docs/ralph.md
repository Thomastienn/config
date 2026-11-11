# Ralph runners

`ralph` and `ralph-afk` work in any Git checkout that has Ralph and Beads set
up. Run them from anywhere inside the checkout. They live in `ralph-tui/bin/`
and are linked into `~/.local/bin` by setup (extras only).

A project needs `.ralph-tui/epics`: the epic IDs Ralph may work on, one per
line in the order to work them, `#` for comments. Its `.ralph-tui/config.toml`
is optional; global defaults are in `ralph-tui/config.toml`.

## Agents

`ralph-tui/agents` lists every agent the runners can use, one per line:

```text
name|work model|probe
```

- `name`: a Ralph agent plugin, as listed by `ralph-tui plugins agents`.
- `work model`: passed to Ralph as `--model`. `RALPH_<NAME>_MODEL` overrides it
  for one run (`RALPH_CODEX_MODEL`, `RALPH_GITHUB_COPILOT_MODEL`).
- `probe`: a cheap one-word request to the agent's own CLI. It runs in `/tmp`
  and the agent counts as usable when the reply contains `pong`.

To add an agent, add a line. Check the probe by hand first, then run one task
with `ralph --agent <name> --iterations 1`. Claude and Codex have done real
Ralph runs. Cursor has only had its probe checked.

## ralph

```bash
ralph                                  # first epic in .ralph-tui/epics, project's default agent
ralph my-epic --iterations 10
ralph --agent codex                    # Codex with its model from the agents table
ralph --agent codex --takeover         # stop the Ralph running here, then start
```

`--agent <name>` without `--model` adds that agent's work model, because the
model in a project's `config.toml` belongs to its default agent. Other options
go to `ralph-tui run --headless` unchanged.

`--takeover` stops the Ralph that holds `.ralph-tui/ralph.lock` in this checkout
before starting. The helper checks the lock against the live process, hostname
and checkout before it signals anything. Ralph gets 30 seconds to stop, then its
child agents are terminated, and killed 5 seconds later if needed. The
interrupted task keeps its claim so `beads-resume` recovers its pending edits.
Old session files are archived under `.ralph-tui/reports/takeover-*`, so the new
run needs no prompt. Do not combine `--takeover` with `--force` or `--resume`.

## ralph-afk

Keeps the backlog moving while nobody is present. Start it once, in tmux or
with `nohup`:

```bash
ralph-afk                              # whichever of Claude or Codex has usage
RALPH_AFK_SCHEDULE='00-07=codex 07-24=claude,codex,cursor' ralph-afk
ralph-afk my-epic other-epic           # only these epics, in this order
```

It is the only launcher, so Ralph's single-session lock never blocks it. Each
cycle it starts one `ralph --takeover --iterations 1` run (one task) and waits
for it to end. A Ralph already running in the checkout, including an
interactive one, is stopped by that first takeover. A second `ralph-afk` in the
same checkout is refused.

Before each run it probes the scheduled agents and uses the first that answers.
It stays on the agent that ran last and switches only when that agent stops
answering. Ralph 0.12.0's own `fallbackAgents` is not used: it does not
recognise subscription usage-limit errors, so a limited agent fails every few
seconds until the iteration limit. If no scheduled agent answers, or a run ends
within two minutes (limit reached at once, startup failure, crash), it waits
`RALPH_AFK_WAIT` seconds (default 600) and checks again. That also covers a
limit that resets while you sleep.

During a run it repeats the probe every `RALPH_AFK_WAIT` seconds. If the CLI
stops answering (usage limit, auth or network), it stops that Ralph and its
child agents through the takeover helper and checks the scheduled agents again
at once. The next available agent resumes the unfinished task and its pending
edits through `beads-resume`. Task output that mentions limits does not trigger
a switch. A probe times out after 180 seconds. If the stop fails, the
supervisor keeps that run and tries again after the next probe. A cheap-model
probe can miss a limit that applies only to the work model.

With no arguments it works the epics in `.ralph-tui/epics` from top to bottom:
each cycle takes the first epic that has a ready or in-progress issue. It stops
when none has one; blocked issues do not count.

`RALPH_AFK_SCHEDULE` is a space-separated list of `FROM-TO=agents` windows in
local hours, with agents tried in order. The default is `00-24=claude,codex`.
An hour outside every window runs nothing. Write a window that crosses midnight
as two (`22-24=codex 00-06=codex`). The schedule is read when a task starts; a
running task is not interrupted at a window boundary.

## Checks

```bash
node --test ralph-tui/test/*.test.mjs
```

The tests use fake CLIs in a temporary checkout. They make no model calls.
