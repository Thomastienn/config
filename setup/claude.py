"""Portable Claude Code preferences; credentials, sessions and project state stay in the local home."""

import copy
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parent.parent / "claude"


def merge(current, defaults):
    for key, value in defaults.items():
        if isinstance(value, dict):
            if not isinstance(current.setdefault(key, {}), dict):
                raise ValueError(f"Claude setting {key} must be an object; kept local settings")
            merge(current[key], value)
        else:
            current[key] = value
    return current


def configuration(home, backup=None):
    path = home / ".claude/settings.json"
    current = json.loads(path.read_text()) if path.exists() else {}
    desired = merge(copy.deepcopy(current), json.loads((ROOT / "settings.json").read_text()))
    if current == desired:
        return []
    if backup is not None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(desired, stream, indent=2)
                stream.write("\n")
            if path.exists() or path.is_symlink():
                backup(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print("Applied portable Claude Code settings; local state preserved.")
    return ["Claude Code: portable settings differ"]


def install(home, cache, run):
    spec = json.loads((ROOT.parent / "setup/sources.json").read_text())["claude-code"]
    command = shutil.which("claude") or str(home / ".local/bin/claude")
    if not Path(command).is_file():
        cache.mkdir(parents=True, exist_ok=True)
        installer = cache / "claude-install.sh"
        # shortcut: the official installer is unpinned because it tracks the current release; pin a checksum if it must be reproducible.
        run(["curl", "-fsSL", "--retry", "2", spec["installer_url"], "-o", installer])
        run(["bash", installer])
        if not Path(command).is_file():
            raise RuntimeError("Claude Code installation did not publish ~/.local/bin/claude")

    for name, source in spec["skills"].items():
        target = home / ".claude/skills" / name
        if target.is_symlink():
            target.unlink()  # Replace links into other agents' skill trees with Claude's own copy.
        if not (target / "SKILL.md").is_file():
            run(["skills", "add", source, "--global", "--agent", "claude-code", "--copy", "--yes",
                 "--full-depth", "--skill", name])
            if not (target / "SKILL.md").is_file():
                raise RuntimeError(f"Claude skill was not installed: {name}")

    state = home / ".claude.json"
    servers = json.loads(state.read_text()).get("mcpServers", {}) if state.is_file() else {}
    if "codebase-memory-mcp" not in servers and shutil.which("codebase-memory-mcp"):
        run([command, "mcp", "add", "--scope", "user", "codebase-memory-mcp", "--", "codebase-memory-mcp"])

    settings = json.loads((ROOT / "settings.json").read_text())
    for name, item in settings["extraKnownMarketplaces"].items():
        if not (home / ".claude/plugins/marketplaces" / name).is_dir():
            run([command, "plugin", "marketplace", "add", item["source"]["repo"]])
    registry = home / ".claude/plugins/installed_plugins.json"
    installed = json.loads(registry.read_text())["plugins"] if registry.is_file() else {}
    for name, enabled in settings["enabledPlugins"].items():
        if enabled and name not in installed:
            run([command, "plugin", "install", "--scope", "user", name])
