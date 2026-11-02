#!/usr/bin/env python3
"""Toggle Live Captions at the bottom center of the focused workspace."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


def ipc(message, query=False):
    args = ["i3-msg", "-t", message] if query else ["i3-msg", message]
    result = json.loads(subprocess.check_output(args, text=True))
    if not query and not all(reply.get("success") for reply in result):
        raise RuntimeError("Could not position Live Captions.")
    return result


def find_window(node, workspace=None):
    if node.get("type") == "workspace":
        workspace = node["name"]
    props = node.get("window_properties", {})
    if props.get("class") == "livecaptions" and props.get("title") == "Live Captions":
        return node, workspace
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        found = find_window(child, workspace)
        if found:
            return found
    return None


def geometry(rect):
    width = min(1000, int(rect["width"] * 0.8))
    height = min(180, int(rect["height"] * 0.3))
    return width, height, rect["x"] + (rect["width"] - width) // 2, rect["y"] + rect["height"] - height - 24


def main():
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    with (runtime / "live-captions.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        workspace = next(w for w in ipc("get_workspaces", True) if w["focused"])
        window = find_window(ipc("get_tree", True))
        if window and window[1] == workspace["name"]:
            ipc(f"[con_id={window[0]['id']}] move scratchpad")
            return
        if window is None:
            subprocess.Popen(["flatpak", "run", "net.sapples.LiveCaptions"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(100):
                time.sleep(0.1)
                window = find_window(ipc("get_tree", True))
                if window:
                    break
            if window is None:
                raise RuntimeError("Live Captions did not open within ten seconds.")
        target = f"[con_id={window[0]['id']}]"
        ipc(f"{target} floating enable, move scratchpad")
        ipc(f"{target} scratchpad show")
        width, height, x, y = geometry(workspace["rect"])
        ipc(f"{target} border pixel 1, resize set {width} px {height} px")
        # GTK may constrain the requested size; center the actual outer rectangle.
        actual = find_window(ipc("get_tree", True))[0]["rect"]
        rect = workspace["rect"]
        x = rect["x"] + (rect["width"] - actual["width"]) // 2
        y = rect["y"] + rect["height"] - actual["height"] - 24
        ipc(f"{target} move absolute position {x} px {y} px")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Live Captions failed", str(error)])
        raise SystemExit(1)
