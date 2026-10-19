#!/usr/bin/env python3
"""Toggle Firefox's regular profile in the scratchpad while keeping it running."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

MARK = "browser-scratchpad"
CLASS = "firefox"


def browser_windows(node, workspace=None):
    windows = {}
    if node.get("type") == "workspace":
        workspace = node["name"]
    properties = node.get("window_properties", {})
    if (node.get("window") and (properties.get("class") or "").lower() == CLASS
            and properties.get("window_role") == "browser"):
        windows[node["id"]] = dict(node, workspace=workspace)
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        windows.update(browser_windows(child, workspace))
    return windows


def get_tree():
    result = subprocess.run(["i3-msg", "-t", "get_tree"],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_windows():
    return browser_windows(get_tree())


def command(action):
    result = subprocess.run(["i3-msg", action], capture_output=True, text=True, check=True)
    if not all(reply.get("success") for reply in json.loads(result.stdout)):
        raise RuntimeError("i3 window command failed.")


def main(show=False):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    with (runtime / f"dropdown-browser-{os.getuid()}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        existing = get_windows()
        for target, window in existing.items():
            if MARK in window.get("marks", []):
                action = "focus" if show and window["workspace"] != "__i3_scratch" else "scratchpad show"
                command(f"[con_id={target}] {action}")
                return window["window"]

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
                return window["window"]
            if process.poll() not in (None, 0):
                raise RuntimeError("Firefox could not start. Check that firefox opens normally.")
        raise RuntimeError("Firefox did not open within ten seconds. Try again.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="Show and focus without hiding; print the X11 window ID")
    args = parser.parse_args()
    try:
        window = main(args.show)
        if args.show and window:
            print(window)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Window action failed", str(error)])
        raise SystemExit(1)
