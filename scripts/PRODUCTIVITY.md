# Desktop productivity

One-time setup from this checkout:

```sh
sudo apt install --no-install-recommends recollcmd poppler-utils python3-gi
/usr/bin/python3 ~/thomas_config/scripts/install-productivity.py
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

Click the existing Polybar status area to open Eww. **Audio devices** lists outputs
and microphones; selecting one moves active streams as well as changing the default.
Desktop-audio capture streams are preserved when changing microphones.

**Focus** offers 5, 10, or 25 minutes. Name one small next action in the familiar
Rofi prompt, or press Enter to start without writing one. Routine notifications
wait; command results and critical alerts remain visible. Stop anytime. At the end,
choose another session or a 5-minute break. There are no streaks or penalties.
**Save a thought** stores a note for your next break; notes remain until cleared.
The panel shows the latest 20; all notes are stored in
`~/.local/state/thomas-desktop/focus-notes.json`.

Specific plans informed the next-action/parked-thought design:
[Masicampo & Baumeister, 2011](https://pubmed.ncbi.nlm.nih.gov/21688924/).
Optional breaks are supported for fatigue management, not promised performance gains:
[Albulescu et al., 2022](https://doi.org/10.1371/journal.pone.0272460).
Session lengths are practical defaults, not a scientifically optimal schedule.

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

```sh
/usr/bin/python3 scripts/test-productivity.py
/usr/bin/python3 scripts/test-desktop-shortcuts.py
bash -n scripts/command-finished.sh
i3 -C -c i3/config
systemd-analyze --user verify systemd/user/thomas-*.service systemd/user/thomas-*.timer
```

Lid close/resume and actual headphone/microphone routing also need a laptop check;
isolated/headless checks cannot prove those hardware behaviors.
