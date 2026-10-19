# Working in this repository

This is Thomas's Linux Mint / Ubuntu i3 desktop configuration. Preserve the
existing Cozy Mint appearance and workflows unless a change is requested.

- Use the installed Caveman skill by default, until Thomas says `normal mode`
  or `stop caveman`. Write code and documentation normally.
- Follow `~/.codex/RTK.md` when present; prefix shell commands with `rtk`.
- Prefer codebase-memory-mcp graph tools for code discovery. Fall back to `rg`
  for shell/config files, literals, or when this repository is not indexed.
- `setup.sh` is the entry point for recreating the machine. Put one-time
  installers, migrations, package manifests, and captured desktop preferences
  under `setup/`. Keep `scripts/` for helpers used during normal operation.
- Every feature needing installation must be reachable from `setup.sh`.
  Make setup safe to repeat: skip completed work, back up conflicting files,
  and preserve unrelated configuration. Never remove existing config trees.
- Dependency installation is part of completing a feature, even when the
  dependency is already installed on Thomas's machine. Update the appropriate
  manifest: `setup/apt.txt` (desktop), `setup/apt-extra.txt` (optional development),
  `Brewfile`, `setup/flatpaks.txt`, `setup/npm-extra.txt`, or
  `setup/neovim-requirements.txt`. Record source builds/downloads in
  `setup/sources.json` or `setup/assets.json`, with their installation steps
  wired into `setup.sh apply` through `setup/main.py` or `setup/tools.py`.
- Include new config links, settings, and services in setup as needed. Verify
  the installation route and repeat-run behavior using an isolated environment;
  working on the current machine alone is insufficient. Document unavoidable
  manual steps in `README.md` and report any fresh-machine checks not performed.
- This machine is the main host. Finish each feature by applying it live here
 too (install root-owned copies, reload affected helpers); `setup.sh` is how
 other machines sync to this host, not a step left for Thomas.
- Git already provides synchronization. Do not add background sync, automatic
  commits/pushes, or another dotfile manager. After pulling, rerun setup to apply
  installation/settings changes; linked config files update directly.
- Keep machine-specific hardware settings and secrets out of shared defaults.
  Never capture browser profiles, credentials, SSH keys, clipboard contents,
  shell history, or task data into Git.
- Run meaningful checks while working, then remove test files after validation.
  Use `/tmp` for temporary test harnesses. Do not retain or add a permanent test
  suite unless Thomas explicitly asks for one. Keep read-only setup checks.
- Do not restart the live desktop, replace installed tools, or change power/lid
  policies just to validate a refactor. Prefer an isolated home/display/session.
- Preserve unrelated edits. Commit only when asked; inspect staged paths/diff.

See [README.md](README.md) for setup commands and supported scope.
