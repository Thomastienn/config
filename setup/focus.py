"""Register the local Lock In native host; never modify browser profiles."""

import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def registration(home):
    key = json.loads((ROOT / "brave/focus-guard/manifest.json").read_text())["key"]
    extension = "".join(chr(97 + int(char, 16)) for char in hashlib.sha256(base64.b64decode(key)).hexdigest()[:32])
    path = home / ".config/BraveSoftware/Brave-Browser/NativeMessagingHosts/org.thomas.focus.json"
    data = {"name": "org.thomas.focus", "description": "Focus Garden local browser bridge", "type": "stdio",
            "path": str(home / ".local/bin/thomas-focus-browser"), "allowed_origins": [f"chrome-extension://{extension}/"]}
    return path, data


def configure(home, backup=None):
    path, desired = registration(home)
    try:
        if json.loads(path.read_text()) == desired:
            return []
    except (OSError, ValueError):
        pass
    if backup is not None:
        for parent in path.parents:
            if parent == home:
                break
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise RuntimeError(f"Keep foreign browser config intact; resolve this parent first: {parent}")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".focus-host-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(desired, output, indent=2)
                output.write("\n")
            if path.exists() or path.is_symlink():
                backup(path)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        print("Registered Lock In native host. Load brave/focus-guard once in Brave, then click its toolbar icon.")
    return ["Lock In: Brave native host registration differs"]
