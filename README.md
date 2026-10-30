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

Development/AI tools include 9Router 0.5.112. Its user service starts at i3 login
and listens only on `127.0.0.1:20128`; open `http://127.0.0.1:20128/dashboard`.
Setup also starts it immediately when installed. The service runs the bundled
server directly, avoiding the interactive launcher's process cleanup and update
checks. Provider sign-in, passwords and API keys stay in private `~/.9router/`;
configure them locally on each machine. Keep cloud/tunnels disabled for local use.
API keys are optional in the app: enable them if untrusted local clients are a concern.
Use `systemctl --user stop 9router.service` to stop it until next login or setup
application. Running `9router` manually uses upstream's launcher defaults instead
of these service settings.

## Use and update

`Super+Enter`: terminal · `Super+D`: launcher · `Super+F1`: shortcut finder.
Click Polybar controls for audio, network, battery saver and timer.
Eww **Controls → Do not disturb** silences notifications and keeps the latest 30 in
**History**. Its gear opens **Allowed apps**; selected apps can still show popups.
Apps appear after sending a notification. Click a row to save immediately, or use
**Search apps** for a searchable Rofi chooser. Choices stay private on this machine
and survive history clearing. New apps are silenced by default, including critical
alerts. Turning DND off restores new popups without replaying missed ones.
Theme updates preserve DND; restarting Dunst or using `dunstctl reload` resets it
to Off. Opening the app picker never turns DND on.
A rounded **bell-slash icon** appears in Polybar while DND is enabled; click it to turn DND off.
App-exception editing waits while Dunst has a separate notification pause active.

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
