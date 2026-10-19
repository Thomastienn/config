"""Portable Codex preferences; authentication, trust and history stay in the local home."""

from datetime import date, time
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parent.parent / "codex"


def merge(current, defaults):
    for key, value in defaults.items():
        if isinstance(value, dict):
            if not isinstance(current.setdefault(key, {}), dict):
                raise ValueError(f"Configuration setting {key} must be a table; kept local config")
            merge(current[key], value)
        else:
            current[key] = value
    return current


def toml_value(value):
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {toml_value(v)}" for k, v in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, (str, bool, int, float)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    raise ValueError(f"Unsupported Codex setting type: {type(value).__name__}")


def toml_text(data, path=()):
    rows = ["[" + ".".join(json.dumps(k) for k in path) + "]"] if path else []
    rows += [f"{json.dumps(k)} = {toml_value(v)}" for k, v in data.items() if not isinstance(v, dict)]
    for key, value in data.items():
        if isinstance(value, dict):
            rows += ["", toml_text(value, (*path, key)).rstrip()]
    return "\n".join(rows) + "\n"


def configuration(home, backup=None):
    path = home / ".codex/config.toml"
    current = tomllib.loads(path.read_text()) if path.exists() else {}
    desired = merge(copy.deepcopy(current), tomllib.loads((ROOT / "config.toml").read_text()))
    if current == desired:
        return []
    if backup is not None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # shortcut: local TOML comments are not preserved; use a TOML editor if annotations become important.
        text = toml_text(desired)
        if tomllib.loads(text) != desired:
            raise ValueError("Codex config serialization changed values; kept local config")
        fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(text)
            if path.exists() or path.is_symlink():
                backup(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print("Applied portable Codex preferences; local secrets and trust preserved.")
    return ["Codex: portable preferences differ"]


def install(home, run):
    sources = json.loads((ROOT.parent / "setup/sources.json").read_text())
    for spec in sources.values():
        if spec.get("kind") != "skills":
            continue
        source, skills = spec["url"], spec["skills"]
        missing = [name for name in skills if not (home / ".agents/skills" / name / "SKILL.md").is_file()]
        if missing:
            run(["skills", "add", source, "--global", "--agent", "codex", "--yes", "--full-depth", "--skill", *missing])
            unavailable = [name for name in missing if not (home / ".agents/skills" / name / "SKILL.md").is_file()]
            if unavailable:
                raise RuntimeError(f"Skills unavailable from {source}: {', '.join(unavailable)}")

    defaults = tomllib.loads((ROOT / "config.toml").read_text())
    manifests = (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json", ".codex-plugin/marketplace.json")
    for name, spec in defaults["marketplaces"].items():
        directory = home / ".codex/.tmp/marketplaces" / name
        if not any((directory / manifest).is_file() for manifest in manifests):
            run(["codex", "plugin", "marketplace", "add", spec["source"]])
    catalogues = json.loads(subprocess.check_output(
        ["codex", "plugin", "marketplace", "list", "--json"], text=True, timeout=120))
    available = {item["name"] for item in catalogues["marketplaces"]}

    def installed_plugins():
        result = subprocess.check_output(["codex", "plugin", "list", "--json"], text=True, timeout=120)
        installed = {item["pluginId"]: item for item in json.loads(result)["installed"]}
        # Online catalogues can hide legacy local registrations; keep their cached bundles.
        for name in defaults["plugins"]:
            if name in installed:
                continue
            slug, marketplace = name.split("@", 1)
            directory = home / ".codex/plugins/cache" / marketplace / slug
            bundles = list(directory.glob("*/.codex-plugin/plugin.json"))
            if bundles:
                manifest = max(bundles, key=lambda path: path.stat().st_mtime_ns)
                installed[name] = {"version": manifest.parent.parent.name}
        return installed

    installed = installed_plugins()
    added = False
    for name in defaults["plugins"]:
        if name not in installed:
            if name.split("@", 1)[1] not in available:
                print(f"Pending: sign in to Codex, then install {name} through /plugins.")
                continue
            run(["codex", "plugin", "add", name])
            added = True
    if added:
        installed = installed_plugins()
    for name in defaults["plugins"]:
        if name not in installed:
            continue
        item = installed[name]
        slug, marketplace = name.split("@", 1)
        directory = home / ".codex/plugins/cache" / marketplace / slug / item["version"]
        package = directory / "package.json"
        if not package.is_file() or not json.loads(package.read_text()).get("dependencies"):
            continue
        check = subprocess.run(["npm", "ls", "--prefix", str(directory), "--omit=dev", "--depth=0"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode:
            run(["npm", "ci", "--prefix", directory, "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"])
