#!/usr/bin/env python3
"""Toggle Firefox's regular profile, pausing its process group while hidden."""

import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

MARK = "browser-scratchpad"
CLASS = "firefox"


def browser_windows(node, hidden=False):
    hidden = hidden or node.get("name") == "__i3_scratch"
    windows = {}
    properties = node.get("window_properties", {})
    if (node.get("window") and (properties.get("class") or "").lower() == CLASS
            and properties.get("window_role") == "browser"):
        windows[node["id"]] = dict(node, scratchpad_hidden=hidden)
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        windows.update(browser_windows(child, hidden))
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


def browser_group(window):
    result = subprocess.run(["xprop", "-id", str(window["window"]), "_NET_WM_PID"],
                            capture_output=True, text=True, check=True)
    match = re.search(r"=\s*(\d+)\s*$", result.stdout)
    if not match:
        raise RuntimeError("Could not identify the Firefox process.")
    pid = int(match[1])
    process = Path(f"/proc/{pid}")
    executable = (process / "exe").resolve().name
    # A dedicated group keeps stop/continue away from shells and other applications.
    if (pid <= 1 or process.stat().st_uid != os.getuid()
            or executable not in {"firefox", "firefox-bin", "firefox-esr"}
            or os.getpgid(pid) != pid or os.getsid(pid) != pid):
        return None
    return pid


def toggle(target, window):
    group = browser_group(window)
    if group is not None:
        os.killpg(group, signal.SIGCONT)
    command(f"[con_id={target}] scratchpad show")
    windows = get_windows()
    if target not in windows or not windows[target]["scratchpad_hidden"]:
        return
    if any(not other["scratchpad_hidden"] for other in windows.values()):
        return  # The regular profile also has another window outside the scratchpad.
    if group is None:
        raise RuntimeError("Firefox was hidden but could not be paused safely. "
                           "Quit Firefox normally and reopen it with Mod+G to give it a dedicated process group.")
    try:
        os.killpg(group, signal.SIGSTOP)
    except BaseException:
        os.killpg(group, signal.SIGCONT)
        raise


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
                toggle(target, window)
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
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Window action failed", str(error)])
