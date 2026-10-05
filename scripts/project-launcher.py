#!/usr/bin/env python3
"""Open a remembered directory in workspace 1's existing tmux terminal."""

import html
import json
from pathlib import Path
import subprocess

TMUX = "/home/linuxbrew/.linuxbrew/bin/tmux"


def kitty_windows(node, workspace=None):
    if node.get("type") == "workspace":
        workspace = node.get("num")
    if workspace == 1 and node.get("window_properties", {}).get("class") == "kitty":
        yield node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        yield from kitty_windows(child, workspace)


def main_terminal():
    tree = subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True, text=True, check=True)
    terminals = {}
    for node in kitty_windows(json.loads(tree.stdout)):
        prop = subprocess.run(["xprop", "-id", str(node["window"]), "_NET_WM_PID"],
                              capture_output=True, text=True)
        try:
            terminals[int(prop.stdout.rsplit("=", 1)[-1].strip())] = node["id"]
        except ValueError:
            continue
    clients = subprocess.run([TMUX, "list-clients", "-F", "#{client_pid}\t#{session_id}"],
                             capture_output=True, text=True)
    matches = set()
    for line in clients.stdout.splitlines():
        pid_text, session = line.split()
        pid = int(pid_text)
        seen = set()
        while pid > 1 and pid not in seen:
            if pid in terminals:
                matches.add((terminals[pid], session))
                break
            seen.add(pid)
            try:
                status = Path(f"/proc/{pid}/status").read_text()
                pid = int(next(row for row in status.splitlines() if row.startswith("PPid:")).split()[1])
            except (OSError, StopIteration, ValueError):
                break
    if len(matches) != 1:
        raise RuntimeError("Could not identify one main tmux terminal on workspace 1. "
                           "Keep one Kitty attached to your main session there.")
    return matches.pop()


def main():
    result = subprocess.run(["/home/linuxbrew/.linuxbrew/bin/zoxide", "query", "--list"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not read folder history.")
    paths = [Path(line) for line in result.stdout.splitlines() if Path(line).is_dir()]
    if not paths:
        raise RuntimeError("No remembered folders yet. Visit a folder in your terminal first.")
    home = Path.home()
    labels = [str(Path("~") / path.relative_to(home)) if path.is_relative_to(home)
              else str(path) for path in paths]
    choice = subprocess.run(
        ["rofi", "-dmenu", "-i", "-no-custom", "-format", "i",
         "-theme-str", 'entry { placeholder: "Open folder…"; }'],
        input="\n".join(labels), capture_output=True, text=True,
    )
    if choice.returncode != 0:
        return
    folder = paths[int(choice.stdout.strip())]
    if not folder.is_dir():
        raise RuntimeError(f"Folder no longer exists: {folder}")
    container, session = main_terminal()
    subprocess.run([TMUX, "new-window", "-t", session, "-c", str(folder)], check=True)
    focus = subprocess.run(["i3-msg", f"[con_id={container}] focus"],
                           capture_output=True, text=True, check=True)
    if not all(result.get("success") for result in json.loads(focus.stdout)):
        raise RuntimeError("Tmux window created, but could not focus the main terminal.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Folder launcher failed",
                        html.escape(str(error))])
