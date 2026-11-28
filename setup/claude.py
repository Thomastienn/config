"""Install Claude Code, its skills and plugins; settings.json is symlinked via links.json."""

import json
from pathlib import Path
import shutil
import subprocess

import tools


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

    settings = json.loads((ROOT / "settings.json").read_text())
    for name, item in settings["extraKnownMarketplaces"].items():
        if not (home / ".claude/plugins/marketplaces" / name).is_dir():
            run([command, "plugin", "marketplace", "add", item["source"]["repo"]])
    registry = home / ".claude/plugins/installed_plugins.json"
    installed = json.loads(registry.read_text())["plugins"] if registry.is_file() else {}
    for name, enabled in settings["enabledPlugins"].items():
        if enabled and name not in installed:
            run([command, "plugin", "install", "--scope", "user", name])
    blender_mcp(home, cache, command, spec["mcp"]["blender"], run)


def blender_mcp(home, cache, command, spec, run):
    """Official Blender Lab MCP: add-on built into Flathub Blender, server registered for Claude Code."""
    blender = next((path for path in (Path("/var/lib/flatpak/exports/bin/org.blender.Blender"),
                                      home / ".local/share/flatpak/exports/bin/org.blender.Blender")
                    if path.exists()), None)
    if blender is None:
        raise RuntimeError("Flathub Blender (org.blender.Blender) is missing; it is listed in setup/flatpaks.txt")
    marker = cache / "installed/blender-mcp"
    listed = subprocess.run([blender, "--command", "extension", "list"], capture_output=True, text=True).stdout
    if not (marker.is_file() and marker.read_text() == spec["rev"] and "mcp [installed]" in listed):
        # Checked out under home because the Flatpak sandbox cannot read the host /tmp.
        source = tools.checkout("blender-mcp", spec, home / ".local/share/thomas-config")
        build = cache / "blender-mcp"
        build.mkdir(parents=True, exist_ok=True)
        run([blender, "--command", "extension", "build", "--source-dir", source / "addon/blender_mcp_addon",
             "--output-dir", build])
        package = max(build.glob("mcp-*.zip"), key=lambda path: path.stat().st_mtime)
        run([blender, "--command", "extension", "install-file", "-r", "user_default", "-e", package])
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(spec["rev"])

    server = f"git+{spec['url']}@{spec['rev']}#subdirectory=mcp"
    current = subprocess.run([command, "mcp", "get", "blender"], capture_output=True, text=True)
    if current.returncode == 0 and server not in current.stdout and spec["url"] in current.stdout:
        run([command, "mcp", "remove", "--scope", "user", "blender"])  # Our pinned server moved to a new rev.
    elif current.returncode == 0:
        return  # Current, or a user-chosen blender server this setup does not own.
    run([command, "mcp", "add", "--scope", "user", "blender", "-e", f"BLENDER_PATH={blender}",
         "--", "uvx", "--from", server, "blender-mcp"])
