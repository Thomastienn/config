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
virtualization packages, use `./setup.sh apply --extras`. This also enables
libvirt and adds your user to its group; log out and back in for group changes.
The desktop setup itself does not install hardware drivers or alter lid policy.

Select **i3** in your login manager after setup. On an existing i3 session, close
the Eww flyout, reload Eww and Dunst, then restart i3 when convenient:

```sh
eww -c ~/thomas_config/eww reload
dunstctl reload
# Super+Shift+R restarts i3 and launches its desktop components.
```

Setup does not restart the running desktop or replace its active processes.
New terminal tabs load the shell configuration. Build installs take effect when
the relevant program is next launched. Generate the lockscreen image once with
`betterlockscreen -u ~/thomas_config/wallpapers/hoppers.png`.

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
| `docs/productivity.md` | PDF search, command alerts, focus, audio, and AFK usage |
| `docs/focus-garden.md` | Study/coding garden, optional reminders, private records, and research |

Focus Garden makes lock-in decisions locally with Decima and known-app rules.
Optional 9router writing adds varied themes, reflections, and reward messages;
window titles stay local. Setup installs the pinned Decima environment and model
through full `./setup.sh apply`. 9router is a separately managed optional tool;
without it, built-in wording is used. See [Focus Garden](docs/focus-garden.md).

To save appearance changes made through desktop settings, run `./setup.sh capture`,
review `git diff`, then commit. Capture reads only the keys already listed in
`setup/desktop/settings.json`; it does not dump the machine's dconf database.
GTK files are linked and can be edited directly. Add new packages to their
manifest deliberately. Avoid blindly exporting `apt-mark showmanual`: this Mint
installation marks thousands of base libraries and old kernels as manual.

Downloads/builds use `~/.cache/thomas-config`; persistent source checkouts live
in `~/.local/share/thomas-config/sources`. Existing Neovim configs are preserved.
APT, Homebrew, Flatpak, and optional development packages track available updates;
this restores the workflow and appearance, not a byte-identical OS image.
The source machine's retired PyPy 3.10 formula is deliberately excluded from
fresh installs; install a currently supported PyPy separately if needed.

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
is preserved. The CPU ceiling limits performance, not CPU utilization or watts;
CPU-heavy jobs can take longer. Picom's decorative effects are removed, while
compositing and VSync stay enabled for reliable rendering.

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
The runtime file disappears at reboot. Existing TLP configuration and charging
limits are preserved; explicit conflicting settings in `/etc/tlp.conf` are
reported rather than overwritten. Stop any competing power manager deliberately
before using this mode. System-file conflicts are backed up under
`/var/backups/thomas-config/<time>/`; user configuration backups are unchanged.

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
- ActivityWatch, Boomer, 9router, personal tools, and work repositories referenced
  by optional shortcuts/autostart are separate installs. Install those if needed.
- Keep SSH keys, tokens, clipboard history, Taskwarrior data, focus notes, and
  coursework outside this repository. Back them up separately when migrating.
- Verify physical lid/sleep behavior and actual audio routing on the new machine.

Installer references: [Homebrew](https://docs.brew.sh/Installation),
[Brave](https://brave.com/linux/), [Eww](https://elkowar.github.io/eww/),
[Picom](https://github.com/yshui/picom), [Dunst](https://dunst-project.org/),
[Nerd Fonts](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.4.0).
