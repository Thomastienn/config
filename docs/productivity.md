# Desktop productivity

One-time setup from this checkout:

```sh
cd ~/thomas_config
./setup.sh apply
```

Reload Eww when its flyout is closed:
`eww -c ~/thomas_config/eww reload`. Reload notification rules and preserve DND with
`/usr/bin/python3 ~/thomas_config/scripts/desktop-controls.py reload-dnd`.
The installer starts only the PDF indexing timer; the AFK service runs on demand.

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

## Quick settings and audio

Click the existing Polybar status area to open Eww. The **Audio** page lists outputs
and microphones; selecting one moves active streams as well as changing the default.
Desktop-audio capture streams are preserved when changing microphones.

The larger quick-settings panel has **Controls**, **Audio**, and **History**
pages. Select a page directly; there are no collapsed sections or nested scroll
areas. Tab/Shift+Tab and Enter/Space work throughout. The panel fits the display
height and each page scrolls when needed. Click outside or use the close button
to dismiss it. Opening it again returns to Controls.

## AFK

**AFK · keep awake** is a manual toggle, with no expiry timer. A persistent amber
**AFK** label appears in Polybar while enabled; click it to turn the mode off.
It prevents idle locking, blanking, and suspend while the laptop lid is open by
nudging the pointer one pixel and back every minute. It skips nudges while a mouse
button is held. Screen saver, DPMS, and idle-timer settings stay unchanged.
Manual lock and normal lid policy still work. Closing the lid, suspending, or ending
the service turns AFK off; it stays off after resume. Turning it off lets the normal
idle countdown continue from the last pointer movement. Screen-on power use
increases; thermal controls are unchanged.

If the service reports a problem, inspect `journalctl --user -u thomas-afk.service`.
`systemctl --user stop thomas-afk.service`
stops the nudges and clears the AFK indicator. Old saved display/idle settings are
still restored when recovering state left by the previous implementation.

## Checks

Run `./setup.sh check` for installation differences, and `i3 -C -c i3/config`
for i3 syntax. See [the setup guide](../README.md) for applying changes after a pull.

Lid close/resume and actual headphone/microphone routing also need a laptop check;
isolated/headless checks cannot prove those hardware behaviors.
