#!/usr/bin/env python3
"""Toggle Firefox's regular profile as a scratchpad without changing its tabs."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MARK = "browser-scratchpad"
CLASS = "firefox"


def browser_windows(node):
    windows = {}
    properties = node.get("window_properties", {})
    if (node.get("window") and (properties.get("class") or "").lower() == CLASS
            and properties.get("window_role") == "browser"):
        windows[node["id"]] = node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        windows.update(browser_windows(child))
    return windows


def get_tree():
    result = subprocess.run(["i3-msg", "-t", "get_tree"],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_windows():
    return browser_windows(get_tree())


def focused_window(node):
    if node.get("focused"):
        return node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        focused = focused_window(child)
        if focused is not None:
            return focused
    return None


def command(action):
    result = subprocess.run(["i3-msg", action], capture_output=True, text=True, check=True)
    if not all(reply.get("success") for reply in json.loads(result.stdout)):
        raise RuntimeError("i3 window command failed.")


def close_focused():
    focused = focused_window(get_tree())
    if focused is not None:
        action = "move scratchpad" if MARK in focused.get("marks", []) else "kill"
        command(f"[con_id={focused['id']}] {action}")


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    with (runtime / f"dropdown-browser-{os.getuid()}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        existing = get_windows()
        for target, window in existing.items():
            if MARK in window.get("marks", []):
                command(f"[con_id={target}] scratchpad show")
                return

        process = subprocess.Popen(["firefox"], start_new_session=True)
        for _ in range(100):
            time.sleep(0.1)
            candidates = [window for target, window in get_windows().items() if target not in existing]
            if candidates:
                # Session restore may open several windows; float the focused one.
                window = next((window for window in candidates if window.get("focused")), candidates[0])
                target = window["id"]
                command(f"[con_id={target}] mark --add {MARK}, floating enable, move scratchpad")
                command(f"[con_id={target}] scratchpad show, resize set 60 ppt 75 ppt, move position center")
                return
            if process.poll() not in (None, 0):
                raise RuntimeError("Firefox could not start. Check that firefox opens normally.")
        raise RuntimeError("Firefox did not open within ten seconds. Try again.")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--close"]:
            close_focused()
        else:
            main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Window action failed", str(error)])
