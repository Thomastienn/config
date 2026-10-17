# Desktop productivity

One-time setup from this checkout:

```sh
cd ~/thomas_config
./setup.sh apply
```

Restart i3 once (`Super+Shift+R`) so xidlehook gains its control socket. This restarts
the bar through the existing i3 configuration. Reload Eww when its flyout is closed:
`eww -c ~/thomas_config/eww reload`. Reload notification rules with `dunstctl reload`.
The installer starts only the PDF indexing timer; focus and AFK services run on demand.

## PDF contents

`Super+Ctrl+P` still opens document filenames. **Ctrl+Tab** switches to PDF contents
and back, keeping your query. Enter search words, then select a matching PDF.
Submitting text that matches no filename also switches to the content query.
Escape from results returns to the query; Escape from the query closes search.
**Ctrl+R** in the content query starts an index refresh.

The folder registry is `recoll/recoll.conf`: add locations to `topdirs`, quoting
paths with spaces, then refresh. It starts with `~/ucalgary` and `~/Documents`.
PDFs throughout those folders are searchable, including textbooks and assignments.
Hidden/build folders and symlinked directory trees are skipped. Image-only scans
need OCR and won't have searchable text. First indexing can take a while.

The native Recoll index lives in `~/.cache/thomas-pdf-search/`; private configuration
in `~/.config/thomas-pdfs/` points to the registry. Refresh runs at login and every
15 minutes, at low CPU/I/O priority. No continuously running file watcher is added.

## Command results

Local foreground commands taking at least 30 seconds notify when their tmux pane
or terminal is not focused. Notifications show executable name, result, duration,
and tmux location, without arguments or output. Interactive editors, pagers,
SSH sessions, and Ctrl+C cancellation are excluded. Background jobs and commands
inside a remote SSH shell are outside this feature.

New shell tabs load hooks automatically. For an existing ble.sh tab:

```sh
source ~/thomas_config/scripts/command-finished.sh
```

## Focus and audio

Click the existing Polybar status area to open Eww. The **Audio** page lists outputs
and microphones; selecting one moves active streams as well as changing the default.
Desktop-audio capture streams are preserved when changing microphones.

The larger quick-settings panel has **Controls**, **Audio**, **Focus**, and **History**
pages. Select a page directly; there are no collapsed sections or nested scroll
areas. Tab/Shift+Tab and Enter/Space work throughout. The panel fits the display
height and each page scrolls when needed. Click outside or use the close button
to dismiss it. Opening it again returns to Controls.

Click **Focus** in Polybar, or press **Super+Ctrl+F**, to open
[Focus Garden](focus-garden.md). Choose Study or Coding, give one next action,
select work windows/exact Brave pages, then start 5, 10, or 25 minutes. The local
Brave extension must be paired first. Required typed check-ins arrive every five
minutes; unanswered prompts pause credit. New resource access needs a reason and
a ten-second model review, and expires after five minutes if granted. Unrelated
or unreviewed requests stay blocked. Click rows to check multiple resources, then
Start. Normal ending has a ten-second wait; **Emergency end** or
**Super+Ctrl+Shift+F** is immediate. Routine notifications
wait while command results and critical alerts remain visible. Plants grow from
credited time, with no decay or lost streaks. Wins, breaks, and reminders remain
optional. See the guide for extension installation and strict-mode limits.
**Save a thought** stores a note for your next break; notes remain until cleared.
The panel shows the latest 20; all notes are stored in
`~/.local/state/thomas-desktop/focus-notes.json`.

The [Focus Garden guide](focus-garden.md#research-and-design-decisions) explains
the research, practical defaults, and limits behind these choices.

## AFK

**AFK · keep awake** is a manual toggle, with no expiry timer. A persistent amber
**AFK** label appears in Polybar while enabled; click it to turn the mode off.
It prevents idle locking, blanking, and suspend while the laptop lid is open.
Manual lock and normal lid policy still work. Closing the lid, suspending, or ending
the service turns AFK off; it stays off after resume. Turning it off restarts the
normal idle countdown. Screen-on power use increases; thermal controls are unchanged.

If a service reports a problem, inspect `journalctl --user -u thomas-afk.service`
or `journalctl --user -u thomas-focus.service`. `systemctl --user stop thomas-afk.service`
restores the saved display/idle settings, including after a worker crash.

## Checks

Run `./setup.sh check` for installation differences, and `i3 -C -c i3/config`
for i3 syntax. See [the setup guide](../README.md) for applying changes after a pull.

Lid close/resume and actual headphone/microphone routing also need a laptop check;
isolated/headless checks cannot prove those hardware behaviors.
