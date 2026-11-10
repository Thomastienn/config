# Working in this repository

This is Thomas's Linux Mint / Ubuntu i3 desktop configuration. Preserve the
existing Cozy Mint appearance and workflows unless a change is requested.

- Do not use Beads (`bd`) here. Track work in the conversation, without
  task-tracking files.
- Most files are shell/config: use `rg` for those, for literals, or when the
  repository is not indexed; use codebase-memory-mcp for code.
- Keep `README.md` compact: i3 overview, core features, requirements, setup and
  update commands, basic usage. Feature guides, implementation details,
  troubleshooting, and manual steps go under `docs/`, linked from the README.
- `setup.sh` recreates the machine. One-time installers, migrations, package
  manifests, and captured desktop preferences live under `setup/`; `scripts/`
  holds helpers used during normal operation.
- A feature is complete only when `setup.sh` installs everything it needs, even
  if already installed here: config links, settings, services, and dependencies
  in the right manifest (`setup/apt.txt` desktop, `setup/apt-extra.txt` optional
  development, `Brewfile`, `setup/flatpaks.txt`, `setup/npm-extra.txt`,
  `setup/neovim-requirements.txt`). Record source builds/downloads in
  `setup/sources.json` or `setup/assets.json`, wired into `setup.sh apply`
  through `setup/main.py` or `setup/tools.py`.
- Setup must be safe to repeat: skip completed work, back up conflicting files,
  preserve unrelated configuration, never remove existing config trees.
- Verify the install route and repeat runs in an isolated home/display/session,
  not only on this machine. Use `/tmp` for harnesses and remove test files
  afterwards; add no permanent test suite unless asked (keep read-only setup
  checks). Report fresh-machine checks not performed.
- This machine is the main host: finish each feature by applying it live here
  (install root-owned copies, reload affected helpers). Do not restart the live
  desktop, replace installed tools, or change power/lid policies just to
  validate a refactor.
- Git is the sync. No background sync, automatic commits/pushes, or another
  dotfile manager. After pulling, rerun setup; linked config files update
  directly.
- Preserve unrelated edits. Commit only when asked; inspect staged paths/diff.

## Secrets and local files

- Keep machine-specific hardware settings and secrets out of shared defaults.
  Never put browser profiles, credentials, SSH keys, clipboard contents, shell
  history, or task data in Git.
- Treat `local/`, real `.env` files, credentials, tokens, and private keys as
  opaque: never read, search, print, summarize, or copy their contents into
  context, logs, messages, examples, or shared files, including via scripts or
  symlinks. Exclude `local/`, `.env`, and `.env.*` from broad searches.
- Learn private settings from `*.example` / `*.sample` templates outside
  `local/` (calendar: `themes/calendar.example`), with dummy values in tests.
- Allowed without opening private files: existence/permission checks and
  explicitly requested moves. Applications may load their own private config.

See [README.md](README.md) for setup commands and supported scope.
