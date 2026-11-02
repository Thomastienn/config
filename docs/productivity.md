# Desktop productivity

One-time setup from this checkout:

```sh
cd ~/thomas_config
./setup.sh apply
```

Reload Eww when its flyout is closed:
`eww -c ~/thomas_config/eww reload`. Reload notification rules and preserve DND with
`/usr/bin/python3 ~/thomas_config/scripts/desktop-controls.py reload-dnd`.
The installer starts PDF indexing and the protected Login History service; the AFK
service runs on demand.

## Login history

Open **Login History** from the application launcher or press
**Super+Ctrl+Shift+L**. After `setup.sh apply` (or `apply --configs-only` after a
pull), its initial setup asks for administrator authorization, your own application
password of at least 12 characters, and the previous vault password when migrating
an existing installation. Existing encrypted records and keys are preserved.
Save the displayed recovery code **off this laptop**. Neither password nor the
recovery code is written to an application log or saved as plaintext.

Initial tracking is **Off**. In **Eww → Controls → Login tracking**, enter your
application password to turn it On or Off. On records the next new i3 session;
enabling does not immediately take a photo. Off stops future collection, preserves
existing history, and keeps seven-day expiry running. Canceling or entering a wrong
password leaves the setting unchanged. The flag survives reboot. **Unavailable**
means the protected service cannot be reached; it does not mean tracking is Off.

A new local i3/X11 login and each successful Betterlockscreen unlock are recorded.
Manual, idle and suspend/lid locking use the same foreground locker wrapper.
Only a successful foreground locker exit counts as an unlock; failed startup,
a killed locker and version/help queries do not. Repeated logins in the same
session are deduplicated for seven days; unlocks are separate events.

Failed local password attempts are read from native `pam_unix` journal messages
for LightDM and i3lock, using trusted process/UID fields rather than application
names supplied in a message. No PAM configuration or password verification is
changed. The current Mint password stack emits these messages. Other display
managers, lockers or authentication modules (for example fingerprint-only failures)
need their own integration; they are not silently labeled as supported. Canceled
prompts without a native authentication-failure result are not marked Failed.
LightDM failures may precede session creation; an unknown attempted username is
shown as unknown. Successful login logging covers the configured i3 account.

Capture saves the first frame without an added warm-up delay, then closes the camera.
Camera startup and processing still take time; exposure may be unsettled in changing light.
The camera normally uses its activity LED; a locally calibrated indicator profile
temporarily suppresses it during capture and restores its previous state afterward.
A busy/unavailable camera stores an error
alongside the event. Photos are taken after the result is observed, so they may
show someone after they have moved away from the password prompt. No microphone
or continuous video recording is used.

The viewer groups records by local date, with local time and UTC offset. Enter a
date (`YYYY-MM-DD`) or search term and press Enter to filter. Choose **Event**
(All events / Login / Unlock) and **Result** (All results / Success / Failed) to
filter immediately. Older login records appear as Login / Success. Select a record
for its details. Photos start hidden behind a crossed-eye icon and **Photo hidden**
label. **Show photo** reveals only the selected photo; **Hide photo** conceals it
again. **Show all photos** reveals photos as you select records until unchecked.
Each new viewer starts with photos hidden. Missing photos show **No photo captured**.
**Delete selected** asks for confirmation; no recovery flow clears the database.
Closing the viewer ends its authenticated connection; five minutes without service
activity closes it automatically.

Records include account, hostname, local time/timezone, logind session/seat/TTY,
boot ID, uptime, active network connection names and local IP addresses. These
identify an account/session rather than proving who used it. Location is unavailable
without a GPS source; no coordinates are guessed and no external location lookup
is made.

**Forgot password** accepts your off-laptop recovery code and a new application
password. Successful recovery preserves all unexpired history, encryption keys and
the On/Off flag. It invalidates open authenticated sessions and the old recovery
code, and shows a new code to save. Wrong codes and cancellation change nothing.
Attempts are rate limited without permanent lockout. **New recovery code** in the
unlocked viewer replaces a lost code without erasing history. Losing both password
and recovery code has no unauthenticated reset option.

The root-owned service runs as the dedicated `i3-login-log` system account. It owns
`/var/lib/i3-login-log` (`0700`) and its files (`0600`). The SQLCipher database and
sealed photo/metadata records remain encrypted. Only salted Argon2id password and
recovery verifiers persist; data keys are separate from these verifiers, so recovery
does not require recreating the database. The desktop communicates through a local
Unix socket checked against the configured account's kernel peer credentials.
Eww receives only tracking status. The protected service also receives system
journal read access for native PAM failures; only selected event fields enter
the encrypted history. No network listener is added.

Ordinary desktop applications cannot directly read those keys or change the
protected setting. This is not protection against root, a compromised backend, or
malware reading input/windows in an unlocked X11 session. Desktop login/unlock
hooks can be disabled or forged by software already running as the desktop user, so this is not an unskippable or tamper-proof OS audit.
Already copied files,
backups and filesystem snapshots cannot be revoked. After verified migration,
unchanged old live key/database/vault files are removed; changed source files are
preserved and flagged for administrator cleanup.

The failure monitor follows new journal events, with no historical backfill after
service downtime. Tracking Off suppresses both successful and failed events,
including camera access. Re-enabling does not import failures that occurred while
Off. The viewer reports **Failure monitor unavailable** if its reader is down.
Native system authentication journals remain governed by the OS's own retention;
this feature does not delete them or record typed passwords.

Records expire after seven elapsed days, regardless of daylight-saving changes.
The service excludes expired records from queries and prunes every five minutes,
even while tracking is Off. Nothing wakes a sleeping laptop solely to prune.
SQLCipher secure deletion is enabled. Photos are decoded in viewer memory;
no plaintext photo files or thumbnails are written.

```sh
i3-login-log view
i3-login-log list --date 2026-10-31 --search wifi
i3-login-log list --event unlock --result failure
i3-login-log toggle
i3-login-log recover
systemctl status i3-login-log.service i3-login-log.socket
```

Dependencies and root-owned service copies are installed through `setup.sh apply`.
Config-only setup also updates these copies and installs missing native SQLCipher.
Administrator authentication is required for system installation and initial
enrollment; enter secrets only in the local dialogs or hidden password prompt.
Repeat setup preserves enrollment, keys, history and tracking state.
The fixed camera device defaults to `/dev/video0`; administrator-owned
`/etc/i3-login-log.json` can select another `/dev/videoN`, then rerun setup to update
its device permission.

An existing private `~/.config/i3-login-log/camera.json` calibration is migrated
into the administrator-owned configuration on setup, only for the same device.
Repeat setup preserves that installed profile. Other machines keep the normal LED
unless separately calibrated; no laptop identifiers or calibration are shared in Git.
The restored Sonix method checks USB ID, revision, laptop model, controller ID and
GPIO state before temporarily disabling GPIO bit 0's output direction. It uses the
[Linux UVC extension interface](https://docs.kernel.org/userspace-api/media/drivers/uvcvideo.html)
and the [published Sonix register protocol](https://github.com/Kurokesu/C1_SONIX_Test_AP/blob/master/sonix_xu_ctrls.c).

Capture saves the original direction in protected `camera-gpio.json` before
changing it. Normal completion and failures restore and verify that value after
closing capture. The systemd service also retries restoration after stopping,
including a forced kill, and before starting again. Failed restoration retains
the recovery record and blocks further captures. Device loss or firmware errors
can still prevent restoration; the GPIO method is specific to calibrated hardware.

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
