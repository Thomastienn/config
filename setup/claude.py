"""Install Claude Code, its skills, MCP server and plugins; settings.json is symlinked via links.json."""

import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent.parent / "claude"


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
