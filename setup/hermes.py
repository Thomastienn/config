"""Portable Hermes preferences; credentials, conversations and learned state stay local."""

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from codex import merge


ROOT = Path(__file__).resolve().parent.parent


def configuration(home, backup=None):
    try:
        import yaml
    except ImportError:
        if backup is None:
            return ["Hermes: python3-yaml missing; run setup.sh apply"]
        raise RuntimeError("Hermes configuration needs python3-yaml; run setup.sh apply") from None

    path = home / ".hermes/config.yaml"
    try:
        current = yaml.safe_load(path.read_text()) if path.exists() else {}
        defaults = yaml.safe_load((ROOT / "hermes/config.yaml").read_text())
    except yaml.YAMLError:
        raise ValueError("Invalid Hermes YAML; kept local config") from None
    if current is None:
        current = {}
    if not isinstance(current, dict) or not isinstance(defaults, dict):
        raise ValueError("Hermes config must be a mapping; kept local config")
    desired = merge(copy.deepcopy(current), defaults)
    if current == desired and (not path.exists() or path.stat().st_mode & 0o777 == 0o600):
        return []
    if backup is not None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # shortcut: YAML comments are not preserved; use a round-trip editor if annotations become important.
        text = yaml.safe_dump(desired, allow_unicode=True, sort_keys=False)
        if yaml.safe_load(text) != desired:
            raise ValueError("Hermes config serialization changed values; kept local config")
        fd, temporary = tempfile.mkstemp(prefix=".config-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(text)
            if path.exists() or path.is_symlink():
                backup(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print("Applied portable Hermes preferences; local credentials and state preserved.")
    return ["Hermes: portable preferences or config permissions differ"]


def install(home, cache, run):
    if not shutil.which("ollama"):
        brew = Path("/home/linuxbrew/.linuxbrew/bin/brew")
        run([brew, "bundle", "install", "--no-upgrade", f"--file={ROOT / 'setup/hermes.Brewfile'}"])
        print("Ollama installed. Start its server and pull qwen3.5:9b; see README.md.")

    spec = json.loads((ROOT / "setup/sources.json").read_text())["hermes"]
    executable = home / ".local/bin/hermes"
    command = str(executable) if executable.is_file() else shutil.which("hermes")
    env = {**os.environ, "HOME": str(home), "HERMES_HOME": str(home / ".hermes")}
    if not command:
        cache.mkdir(parents=True, exist_ok=True)
        installer = cache / "hermes-install.sh"
        if not installer.exists() or hashlib.sha256(installer.read_bytes()).hexdigest() != spec["installer_sha256"]:
            run(["curl", "-fL", "--retry", "2", spec["installer_url"], "-o", installer])
        if hashlib.sha256(installer.read_bytes()).hexdigest() != spec["installer_sha256"]:
            raise RuntimeError("Checksum mismatch: Hermes installer")
        run(["bash", installer, "--commit", spec["rev"], "--non-interactive"], env=env)
        if not executable.is_file():
            raise RuntimeError("Hermes installation did not publish ~/.local/bin/hermes")
        command = str(executable)
    else:
        print("Keep installed Hermes; use hermes update for application upgrades.")

    for name in spec["skills"]:
        if not (home / ".hermes/skills" / name / "SKILL.md").is_file():
            run([command, "skills", "install", name], env=env)
            if not (home / ".hermes/skills" / name / "SKILL.md").is_file():
                raise RuntimeError(f"Hermes skill was not installed: {name}")
