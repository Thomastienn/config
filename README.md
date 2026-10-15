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
`--configs-only` reapplies links, desktop preferences, and user services. Run a
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
| `scripts/` | Runtime desktop helpers |
| `docs/productivity.md` | PDF search, command alerts, focus, audio, and AFK usage |

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
