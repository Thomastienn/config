# Cozy Mint desktop

An i3/X11 setup for **Linux Mint 22.x, x86_64**.

- One theme for desktop, terminal, notifications, widgets and lock screen.
- Polybar, Conky, Rofi, Eww controls, battery saver and timer.
- Kitty/tmux shell, clipboard, screenshots, PDF search and task helpers.
- Optional Neovim config, development tools, Codex and Hermes/Ollama.

## Install

On a fresh Mint installation, open a terminal as your normal user:

```sh
sudo apt update
sudo apt install -y git python3
git clone https://github.com/Thomastienn/config.git ~/thomas_config
cd ~/thomas_config
./setup.sh apply
```

Setup installs dependencies, builds desktop tools, generates the theme and applies
configs/services. Neovim and development/AI tools each prompt **[Y/n]**. Press Enter
to include them, or answer `n` to skip. Existing Neovim configs stay intact.

```sh
./setup.sh apply --yes                    # accept saved/default choices
./setup.sh apply --no-nvim --no-extras     # desktop only
./setup.sh check                          # read-only list of remaining gaps
```

Log out, select **i3** at the login screen, then log in. Set up browser accounts,
extensions and hardware drivers separately. First Firefox launch creates its
profile; rerun config-only setup afterward to apply its styles. AI sign-in and
Ollama model downloads stay local.

## Use and update

`Super+Enter`: terminal · `Super+D`: launcher · `Super+F1`: shortcut finder.
Click Polybar controls for audio, network, battery saver and timer.
Eww **Controls → Do not disturb** hides all notification popups, including critical
alerts, and keeps the latest 30 in **History**. Turning it off restores new popups
without replaying missed ones. Dunst restart or rule reload resets it to Off.

```sh
git pull --ff-only
./setup.sh apply --configs-only           # reuse choices, apply config changes
theme apply                              # reapply selected theme
theme apply themes/my-theme.toml          # switch preset
```

Edit appearance in [`themes/cozy-mint.toml`](themes/cozy-mint.toml). Run full
`apply` again when dependencies change. Conflicts are backed up under
`~/.local/state/thomas-config/backups/`; reruns preserve unrelated files.

[Desktop details](docs/desktop.md) · [Productivity helpers](docs/productivity.md)
