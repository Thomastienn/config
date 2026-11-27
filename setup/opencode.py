"""Select the generated desktop theme in OpenCode's CLI settings."""

import copy
import json
import os
from pathlib import Path
import tempfile

from codex import merge

DEFAULTS = {"theme": {"name": "desktop"}}


def configuration(home, backup=None):
    path = home / ".config/opencode/cli.json"
    current = json.loads(path.read_text()) if path.exists() else {"$schema": "https://opencode.ai/v2/cli.json"}
    if not isinstance(current, dict):
        raise ValueError("OpenCode cli.json must be an object; kept local config")
    desired = merge(copy.deepcopy(current), DEFAULTS)
    if current == desired:
        return []
    if backup is not None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".cli-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(json.dumps(desired, indent=2) + "\n")
            if path.exists() or path.is_symlink():
                backup(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print("Selected the desktop theme in OpenCode CLI settings.")
    return ["OpenCode: desktop theme not selected"]
