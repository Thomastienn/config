# Thomas's Linux desktop

Cozy Mint on i3/X11. Git stores the configuration; `setup.sh` installs and applies
the parts that Git alone cannot restore. Target: **Linux Mint 22.x** or **Ubuntu
24.04+**, with the closest appearance on Mint. Run setup as your normal user.

## New machine

Install Git and Python 3, clone this repository into `~/thomas_config`, then:

```sh
cd ~/thomas_config
./setup.sh                 # show the plan; change nothing
./setup.sh apply           # install and configure the desktop
./setup.sh check           # list remaining differences; nonzero while gaps remain
```

`apply` asks for sudo for system packages. It installs the APT manifest, the
`Brewfile`, the recorded Flatpak apps, and pinned builds of Picom 12.5, Dunst,
Eww, ble.sh, i3lock-color, betterlockscreen, and tmux plugins. It installs the
same ComicShannsMono font files as this machine, the Mint themes/cursors, config
links, GTK/GSettings/CopyQ preferences, Firefox styles, and PDF indexing services.
Source builds can take time. Rerun after a failure; successful builds are skipped.

For the previous installer's coursework, Neovim Python tools, coding CLIs, and
virtualization packages, Codex, and Hermes/Ollama, use `./setup.sh apply --extras`. This also enables
libvirt and adds your user to its group; log out and back in for group changes.
The desktop setup itself does not install hardware drivers or alter lid policy.

Select **i3** in your login manager after setup. When the selected theme or its
templates change, setup refreshes supported running desktop components without
restarting the i3 session. It preserves Battery Saver and the running Conky panel
selection. Browsers and existing shells are left open; setup reports their
remaining reload steps. New terminal tabs load the shell configuration. Build
installs take effect when the relevant program is next launched.

Qt 5 apps such as Flameshot use GTK file dialogs through `qt5-gtk-platformtheme`.
The setting lives in `profile` so desktop apps inherit it after login. Flameshot's
screenshot shortcuts also set it explicitly; reload i3's config to apply those
without logging out. Other Qt apps need a new login to inherit the setting.

Kdenlive's application entry uses 96 DPI and a scale factor of 1 so it opens at
100% from Rofi while the rest of the desktop keeps its configured scaling.
Setup installs Kdenlive and links `setup/desktop/org.kde.kdenlive.desktop` into
`~/.local/share/applications/`. Close and reopen Kdenlive after applying the link.

## After pulling on another machine

```sh
git pull --ff-only
./setup.sh apply --configs-only
./setup.sh check
```

Most configs link directly to this checkout, so Git changes reach them at once.
`--configs-only` reapplies links, desktop preferences, user services, and the
protected Battery Saver helper when its installed copy differs. That update
can ask for sudo. Run a
full `apply` when package manifests or source revisions change. Git commits and
pushes remain explicit; there is no additional synchronization service.

`./setup.sh link` changes only config links. It is useful for a headless home
restore or inspecting the resulting links before applying desktop preferences.
Conflicting files are moved into `~/.local/state/thomas-config/backups/<time>/`,
with their original relative paths. Existing config directories are merged one
file at a time; unrelated files survive. A correct existing link is left alone.
To restore a backup, remove the corresponding managed link and move the saved
file back to its original path. Do not delete an entire config directory.

## What lives where

| Location | Purpose |
| --- | --- |
| `setup.sh` | Single entry point |
| `setup/main.py`, `setup/tools.py` | One-time/repeatable installation code |
| `setup/links.json` | Repository files and their home destinations |
| `setup/apt*.txt`, `Brewfile`, `setup/flatpaks.txt` | Reviewed package lists |
| `setup/sources.json`, `setup/assets.json` | Pinned desktop revisions and asset checksums |
| `setup/desktop/` | GTK files and allowlisted GSettings/CopyQ preferences |
| `codex/` | Portable Codex preferences and global instructions |
| `scripts/` | Runtime desktop helpers |
| `docs/productivity.md` | PDF search, command alerts, audio, and AFK usage |

To save appearance changes made through desktop settings, run `./setup.sh capture`,
review `git diff`, then commit. Capture records the shared GTK selection, font,
cursor and dark/light preference in the selected theme; unrelated allowlisted
preferences stay in `setup/desktop/settings.json`. It does not dump dconf.
Edit theme presets rather than generated GTK files. Add new packages to their
manifest deliberately. Avoid blindly exporting `apt-mark showmanual`: this Mint
installation marks thousands of base libraries and old kernels as manual.

Downloads/builds use `~/.cache/thomas-config`; persistent source checkouts live
in `~/.local/share/thomas-config/sources`. Existing Neovim configs are preserved.
APT, Homebrew, Flatpak, and optional development packages track available updates;
this restores the workflow and appearance, not a byte-identical OS image.
The source machine's retired PyPy 3.10 formula is deliberately excluded from
fresh installs; install a currently supported PyPy separately if needed.

## Desktop themes

[`themes/cozy-mint.toml`](themes/cozy-mint.toml) is the first complete preset and
the template for new ones. It preserves the existing appearance, including the
different GTK 2 settings, terminal ANSI colors and Lato lockscreen fonts.

```sh
cd ~/thomas_config
theme check                         # read-only check of selected preset and output
theme apply                         # reapply the preset named by themes/active
cp themes/cozy-mint.toml themes/halloween.toml
$EDITOR themes/halloween.toml
theme check themes/halloween.toml    # preview differences and missing assets
theme apply themes/halloween.toml
theme apply themes/cozy-mint.toml    # return to the regular theme
```

Only Cozy Mint is included. Presets live directly under `themes/`; use filenames
such as `halloween.toml`. `theme apply FILE` changes the one-line `themes/active`
selector after successful activation. Commit the preset and selector deliberately
to share the choice. After pulling on another machine, `apply --configs-only`
generates and applies that selection. There are no automatic commits or pushes.
If selected assets are missing, activation stops before changing appearance;
install them through the existing setup manifests first. Switching downloads
nothing. `theme check` exits nonzero while generated output differs.

The preset controls colors, wallpaper, fonts, GTK themes, icons, cursors, and
existing bat/Taskwarrior skin names. Layouts, shortcuts, DPI and power behavior
stay in the shared configuration. Login-screen and boot themes are outside this
version. Applications that ignore system themes need their own integration.

Native config paths remain stable through portable symlinks. Their generated
targets live under `${XDG_STATE_HOME:-~/.local/state}/thomas-config/theme/`;
`themes/.generated` is a local setup-managed link, excluded from Git. Change
appearance in TOML and shared app structure in `themes/templates/`, then reapply.
Do not edit generated files. JSON/shell/Lua palette consumers use the same data.
Activation validates and stages all output, rolls back failed file writes, and
reports any remaining app reloads. Separate applications cannot update atomically.

The Neovim bridge is one setup-managed symlink in its existing `lua/plugins/`
folder, even when Neovim lives in another repository. Keep that installed link
untracked there; its source belongs to this repository. It reuses AstroTheme
without changing its lockfile or pinned version. Restart Neovim once after the
first setup to load the bridge. Later switches refresh on focus or through
`:DesktopThemeReload`; without generated data the editor keeps its own theme.

Firefox loads generated CSS on its next restart. Brave keeps its existing theme
folder; reload that theme through `brave://extensions` after switching, or load
the folder again if needed. Existing shells need a new tab/session for prompt,
ble.sh and FZF changes. The switcher never restarts these applications. The
lockscreen image cache rebuilds when wallpaper content changes. Terminal apps
such as Codex can cache their startup colors; relaunch them if colors stay stale.

## ChatGPT context shortcuts

Keep a signed-in ChatGPT chat open in the Firefox scratchpad (`Super+G`). These
shortcuts capture context before showing Firefox and paste into the current draft:

| Shortcut | Context |
| --- | --- |
| `Super+Ctrl+G` | Highlighted text (X11 primary selection) |
| `Super+Shift+G` | Screenshot of a region you select |
| `Super+Alt+G` | Screenshot of the monitor containing the pointer |

Type your question directly in ChatGPT afterward, then send it yourself. Existing
draft text and attachments are preserved. `Super+G` still only toggles Firefox.
Find these bindings by searching “ChatGPT” in `Super+F1`.

`./setup.sh apply` installs the accessibility dependencies and enables desktop
accessibility. On an existing machine with those packages installed, use
`./setup.sh apply --configs-only`, then reload i3's configuration. Firefox uses
your regular profile; sign-in stays local and is not copied by setup. No browser
extension or API key is needed.

Capture is on demand. Screenshots become image attachments rather than OCR text;
attaching them uploads them to ChatGPT. Selected text is appended with a blank
line separating it from an existing draft. Cancelling region selection changes
neither the clipboard nor the browser. Successful captures replace the clipboard;
normal CopyQ history behavior still applies.

The helper verifies a ChatGPT page and a unique editable multiline prompt through
Linux accessibility before pasting. If Firefox shows another website, login,
multiple editable message fields, or an inaccessible prompt, it reports an error
and leaves the captured context on the clipboard for manual pasting. It does not
change tabs, start a new conversation, or submit a message. If accessibility is
unavailable, check the desktop accessibility setting and reopen Firefox when
convenient. ChatGPT website changes can require updating the prompt locator.

## Polybar timer

Open Eww Quick Settings by clicking the clock or status area, then choose
**Controls → Timer & stopwatch**. Its menu starts one countdown or stopwatch at a
time. The timer stays hidden from Polybar until started, then appears beside the
clock. Paused and finished timers stay visible until cleared:

- **Left click:** choose a countdown in minutes (presets or a custom value, up to
  1440), start a stopwatch, pause/resume, or clear. Escape cancels the menu.
- **Middle click:** pause or resume.
- **Right click:** clear and hide the timer from Polybar.

Countdown completion shows **Done** and sends a desktop notification. Seconds
update only while running; paused and idle timers wait for state changes. Elapsed
time includes suspend and ignores wall-clock changes. State stays private in
`$XDG_RUNTIME_DIR/thomas-polybar-timer/` (normally `/run/user/<uid>/`), survives
Polybar reloads, and resets on reboot. Polybar must be running to deliver an alert;
an overdue countdown alerts when the bar next starts.

`./setup.sh apply` already installs Python 3, PyGObject, Rofi, Polybar, and
`notify-send`, and links this feature through the existing checkout and Polybar
links. After pulling, close the Eww flyout, apply config links, then reload Eww
and restart Polybar:

```sh
./setup.sh apply --configs-only
eww -c ~/thomas_config/eww reload
~/.config/polybar/shapes/launch.sh
```

## Codex

`codex/config.toml` stores portable model, reasoning, UI, MCP, marketplace and
plugin preferences. `link`, `apply`, and `apply --configs-only` merge these values
into `~/.codex/config.toml`, backing up changes first. Extra local settings,
browser tokens, project trust, and hook approvals survive. The resulting local
file has mode `600`; rewriting it does not preserve TOML comments. Edit the
repository defaults to carry preference changes to another machine, then rerun
setup after pulling. `check` reports differences without writing anything.

Global `AGENTS.md` and `RTK.md` link directly from `codex/`. The whole `.codex`
directory and its live config are deliberately kept local: Codex writes private
and machine-specific state there.

On a new machine, `./setup.sh apply --extras` also installs Codex, the skills CLI,
and codebase-memory-mcp through `setup/npm-extra.txt`. It restores missing global
skills recorded in `setup/sources.json` and missing plugins from the configured
marketplaces, downloading missing marketplace catalogues first. Existing
skills/plugins are kept. Plugin npm dependencies are
checked and repaired with locked production packages and lifecycle scripts
disabled, including ECC's `js-yaml` dependency. Repeat runs skip completed work.
Registry packages and newly downloaded skills/plugins follow their upstream
versions; plugin caches and `node_modules` are not stored in Git.
The old `compress` skill is covered by `caveman-compress`; an existing local
`compress` installation is retained.

Sign in to Codex and reconnect account-backed apps/MCP servers on the new
machine. If the OpenAI catalogue is unavailable while signed out, setup reports
the Canva and Superpowers plugins as pending; install them through `/plugins`
after signing in. Review plugin hooks in `/hooks`; setup does not transfer hook trust.
Install the Playwright MCP browser extension in Brave, then pair it when prompted.
Its optional extension token stays only in the local config. Custom pet assets,
saved command approvals, conversations, memories and other runtime data require
a separate private backup. Restart Codex when convenient to load changed settings.
See the [official configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic#configuration-precedence).

## Hermes

`hermes/config.yaml` holds portable preferences for the local `qwen3.5:9b`
model, toolsets, terminal, display, memory limits, and manual command approvals.
`link`, `apply`, and `apply --configs-only` merge these into
`~/.hermes/config.yaml`, backing up changes and keeping local credentials,
provider entries, Discord settings, and other unowned keys. The local config
has mode `600`; YAML comments are not preserved. `check` reports differences
without writing files. Settings changed through Hermes stay local until you
deliberately update the repository defaults.

`hermes/SOUL.md` links to `~/.hermes/SOUL.md`. It sets a concise personal-assistant
voice, honors advice-only requests, and requires actual tool results before
reporting saved memory, reminders, or completed actions. The personality overlay
is set to `none`, so the previous surfer preset does not compete with it.
This uses Hermes's [supported SOUL.md customization](https://hermes-agent.nousresearch.com/docs/user-guide/features/personality)
and keeps its built-in tool guidance and model chat template. A prompt cannot
guarantee tool accuracy; test important workflows with the actual local model.

On a new machine, `./setup.sh apply --extras` installs missing Hermes using the
official installer pinned and checksum-checked in `setup/sources.json`. Bundled
skills come with Hermes; the existing optional Impeccable skill is restored via
`hermes skills install impeccable` when missing. That skill follows its upstream
version; existing skill copies are kept. Existing Hermes installations are not
upgraded or replaced; use `hermes update` explicitly.

If Ollama is missing, extras installs the official binaries (including GPU
backends) through the [Homebrew Cask](https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/o/ollama-binary.rb)
recorded in `setup/hermes.Brewfile`. Setup does not start Ollama or change GPU drivers.
Start the local server with `ollama serve` (or your existing service), then run
`ollama pull qwen3.5:9b`. Model weights are downloaded separately and not stored in
Git. If you use a different host or model, update the portable endpoint/model
preferences before applying them there.

The whole `.hermes` home stays local. Credentials (`.env`, `auth.json`), account
allowlists, chats, learned memories, task/cron data, skill usage/archives, browser
profiles, caches, tool binaries, and databases are not copied into this checkout.
Use a separate private backup for that state and reconnect messaging accounts on
new machines. No gateway is enabled or restarted by setup. Start a fresh Hermes
session when convenient to load the prompt and preferences; a running gateway
may need a manual restart.

## Battery Saver

Click the battery or Wi-Fi area in Polybar, then switch **Battery Saver** in
Quick Settings. It is manual, survives sleep and i3 reloads, and resets after
reboot. The equivalent commands are:

```sh
python3 ~/thomas_config/scripts/battery-mode.py on
python3 ~/thomas_config/scripts/battery-mode.py off
python3 ~/thomas_config/scripts/battery-mode.py toggle
python3 ~/thomas_config/scripts/battery-mode.py status
```

The mode selects 60 Hz on supported internal panels without changing resolution,
lowers brightness to at most 20%, turns off keyboard lighting, disables CPU turbo,
prefers CPU energy saving and a supported quiet firmware profile, and caps Intel
CPU performance at 40% where supported. An existing lower CPU ceiling or brightness
is preserved. The ceiling is 40% of maximum turbo, so it can sit below base clock
(about 1.9 GHz on an i7-12700H, base 2.3 GHz); `scaling_max_freq` still shows base
clock. It limits performance, not CPU utilization or watts; CPU-heavy jobs can
take longer. Limits also stay on while charging until Battery Saver is switched
off. Picom's decorative effects are removed, while compositing and VSync stay
enabled for reliable rendering; fullscreen windows such as video bypass the
compositor after one second.

Brave (deb install) gets Energy Saver through a managed policy while the mode is
on, so `brave://settings/performance` shows "Managed by your organization" and
Energy Saver only acts when unplugged. Turning saver off, or rebooting, removes
the policy and returns Brave to its own setting. Brave watches its policy
directory; if `brave://policy` still shows the old state, use **Reload policies**.

All managed Conky panels stop, including weather and calendar/tasks. Scheduled PDF
indexing pauses; an already running index finishes, existing search still works,
and Ctrl+R can request an index manually. Automatic update checks from the panel
use a cached count, or show `Deferred`. Applications, ActivityWatch, clipboard,
network connections, downloads, and active jobs continue running. Turning saver
off restores only the panels and PDF timer that were running beforehand, along
with captured settings except those subsequently adjusted by hand.

After logging out/in once to activate the updated xidlehook configuration, saver
blanks idle displays after two minutes. Audio, fullscreen applications, AFK mode,
and logind idle inhibitors prevent this early blanking. Input wakes the screen;
the existing ten-minute lock and twenty-five-minute suspend timing is unchanged.
Disabled/unavailable DPMS or failed inhibitor checks leave the screen on. Refresh
and brightness changes affect the internal panel only; idle blanking uses DPMS
and therefore affects all displays.

Installation is part of `./setup.sh apply`; an existing machine with TLP and
pkexec already installed can use `./setup.sh apply --configs-only`. No desktop
restart is required for the toggle: reload Eww to expose the new button. The new
idle timer needs one logout/login. Setup starts a small
event-driven user service for display changes and wake events; future i3 logins
start it automatically. It has no periodic polling loop.

TLP remains the sole power manager. The installer copies a fixed helper into
root-owned `/usr/local/libexec`, installs a narrowly scoped Polkit action for the
active local user, and links a dedicated TLP drop-in to a root-owned runtime file.
The runtime file disappears at reboot and is never captured into Git.

`setup/tlp.conf` captures the host's normal TLP preferences: Bluetooth off at
startup and 80% charge-stop thresholds for BAT0/BAT1. Both `apply` and
`apply --configs-only` install it as root-owned `/etc/tlp.conf`, backing up an
existing different file under `/var/backups/thomas-config/<time>/`. Other TLP
drop-ins remain in place; unspecified settings use the installed TLP defaults.
Edit the repository copy and rerun setup to reproduce changes on each machine.
Charge thresholds require hardware support; verify with `sudo tlp-stat -b` on a
new laptop, since some drivers also require a start threshold. Stop any competing
power manager deliberately before using Battery Saver. Explicit settings that
conflict with its temporary overrides are reported rather than silently changed.

Check the button's tooltip or the JSON `status` output for unsupported controls,
manual overrides, and restoration errors. Failed activation attempts roll back;
if restoration is interrupted, run `off` again. Diagnostic Picom output is in
`$XDG_RUNTIME_DIR/thomas-battery-mode/picom.log`. Normal appearance remains the
default after reboot.

The tooltip includes a passive NVIDIA runtime power state when available. It
does not poll `nvidia-smi`, and an active GPU can be legitimate when a GPU app or
a connected display needs it. Wireless/USB policies, GPU drivers, BIOS settings,
and sleep/lid rules are unchanged. Actual battery savings require an unplugged
measurement with a comparable workload; isolated tests do not establish runtime.

### Optional Intel desktop and NVIDIA on-demand

On a supported Intel/NVIDIA laptop, install the distribution's graphics drivers,
then explicitly select hybrid graphics through setup:

```sh
./setup.sh apply --graphics on-demand
# With dependencies already installed:
./setup.sh apply --configs-only --graphics on-demand
```

Ordinary setup does not change graphics profiles. Selection uses `prime-select`
and can update initramfs; it never logs out, restarts the desktop, or reboots.
**Save your work, then log out and back in.** Check `glxinfo -B` for the default
Intel renderer and `xrandr --listproviders` for the NVIDIA offload provider. A
selected on-demand profile does not prove the running desktop has switched.

Launch an OpenGL GPU application explicitly with:

```sh
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia application
```

For Vulkan/EGL, `__NV_PRIME_RENDER_OFFLOAD=1` is sufficient. CUDA applications use
NVIDIA through their own device selection. Check the detected NVIDIA PCI device's
`power/runtime_status` under `/sys/bus/pci/devices` after GPU applications exit:
on battery, supported runtime power management should eventually report
`suspended`. GPU-connected monitors and active GPU clients can prevent suspension.

If logout/login does not activate the profile, report the pending state and reboot
when convenient; setup does not force it. To return to NVIDIA desktop rendering:

```sh
./setup.sh apply --configs-only --graphics nvidia
# Save work, then log out/in (or reboot if needed).
```

Hybrid selection persists across reboots independently of the manual Battery
Saver toggle. Older saver snapshots remain restorable; new limits take effect
on the next activation.

## Remaining machine-specific steps

- Launch Firefox once to create a default profile, then rerun `apply --configs-only`
  to link its CSS and `user.js`. Both native and Ubuntu Snap profile locations
  are detected. Restart Firefox to load the styles.
- Load the [Brave theme](brave/README.md) through `brave://extensions`. Browser
  extensions, sessions, accounts, and logins require browser sync or manual setup.
- Install GPU/laptop drivers using the distribution's tools. Battery names,
  display modes and compositor support depend on hardware. The bar detects
  battery/adapter names; refresh toggling uses the active resolution's supported rates.
  Brightness keeps the existing NVIDIA WMI preference when available and falls
  back to a detected backlight. Touchpads are found by name instead of numeric ID.
- ActivityWatch, Boomer, personal tools, and work repositories referenced
  by optional shortcuts/autostart are separate installs. Install those if needed.
- Keep SSH keys, tokens, clipboard history, Taskwarrior data, and
  coursework outside this repository. Back them up separately when migrating.
- Verify physical lid/sleep behavior and actual audio routing on the new machine.

Installer references: [Homebrew](https://docs.brew.sh/Installation),
[Brave](https://brave.com/linux/), [Eww](https://elkowar.github.io/eww/),
[Picom](https://github.com/yshui/picom), [Dunst](https://dunst-project.org/),
[Nerd Fonts](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.4.0).
