#!/usr/bin/env python3
"""Toggle an i3 scratchpad Kitty with an independent tmux server."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

KITTY = str(Path.home() / ".local/kitty.app/bin/kitty")
CLASS = "task-dropdown"


def find_window(node, hidden_only=False, in_scratchpad=False):
    in_scratchpad = in_scratchpad or node.get("name") == "__i3_scratch"
    if node.get("window_properties", {}).get("class") == CLASS and (not hidden_only or in_scratchpad):
        return node["id"]
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_window(child, hidden_only, in_scratchpad)
        if found is not None:
            return found
    return None


def window_id(hidden_only=False):
    result = subprocess.run(["i3-msg", "-t", "get_tree"],
                            capture_output=True, text=True, check=True)
    return find_window(json.loads(result.stdout), hidden_only)


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    with (runtime / f"dropdown-terminal-{os.getuid()}.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        target = window_id()
        if target is None:
            subprocess.Popen([KITTY, "--class", CLASS, "--title", "Quick terminal",
                              "/home/linuxbrew/.linuxbrew/bin/tmux", "-L", "dropdown",
                              "new-session", "-A", "-s", "scratch"], start_new_session=True)
            for _ in range(50):
                time.sleep(0.1)
                target = window_id(hidden_only=True)
                if target is not None:
                    break
            if target is None:
                raise RuntimeError("Kitty did not open within five seconds. Try again.")
        result = subprocess.run(["i3-msg", f"[con_id={target}] scratchpad show, move position center"],
                                capture_output=True, text=True, check=True)
        if not all(reply.get("success") for reply in json.loads(result.stdout)):
            raise RuntimeError("Could not toggle dropdown terminal.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Dropdown failed", str(error)])
