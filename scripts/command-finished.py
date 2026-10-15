#!/usr/bin/env python3
"""Notify about a finished foreground command when its pane isn't focused."""

import html
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def output(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=3).stdout.strip()


def ancestors(pid):
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            status = Path(f"/proc/{pid}/status").read_text()
            pid = int(next(line.split()[1] for line in status.splitlines() if line.startswith("PPid:")))
        except (OSError, StopIteration, ValueError):
            break
    return seen


def pane_focused(shell_pid, pane):
    window = re.search(r"(?:#|=)\s*(0x[0-9a-fA-F]+|\d+)", output(["xprop", "-root", "_NET_ACTIVE_WINDOW"]))
    if not window or int(window[1], 0) == 0:
        return False
    pid = re.search(r"=\s*(\d+)", output(["xprop", "-id", window[1], "_NET_WM_PID"]))
    if not pid:
        return False
    terminal_pid = int(pid[1])
    if pane:
        clients = output(["tmux", "list-clients", "-F", "#{client_pid}\t#{pane_id}"])
        return any(active == pane and terminal_pid in ancestors(int(client))
                   for line in clients.splitlines() if len(fields := line.split()) == 2
                   for client, active in [fields])
    return terminal_pid in ancestors(shell_pid)


def command_name(text):
    try:
        words = shlex.split(text)
    except ValueError:
        return "Command"
    while words and ("=" in words[0] or words[0] in {"sudo", "command", "builtin", "env", "time", "rtk", "proxy"}
                     or words[0].startswith("-")):
        words.pop(0)
    name = Path(words[0]).name if words else "Command"
    return name if re.fullmatch(r"[\w.+-]+", name) else "Command"


def main(status, elapsed, shell_pid, text):
    name = command_name(text)
    if elapsed < 30 or status == 130 or name in {
        "nvim", "vim", "vi", "nano", "emacs", "less", "more", "man", "ssh", "tmux",
        "htop", "btop", "top", "nnn", "ranger", "bash", "zsh", "fish",
    }:
        return
    pane = os.environ.get("TMUX_PANE", "")
    if pane_focused(shell_pid, pane):
        return
    origin = output(["tmux", "display-message", "-p", "-t", pane,
                     "#{session_name}:#{window_index}.#{pane_index}"]) if pane else "terminal"
    minutes, seconds = divmod(elapsed, 60)
    result = "finished" if status == 0 else f"failed (exit {status})"
    subprocess.run(["notify-send", "-a", "Command finished", "-u", "normal" if status == 0 else "critical",
                    f"{name} {result}", html.escape(f"{minutes}m {seconds:02d}s · {origin}")], check=True)


if __name__ == "__main__":
    try:
        main(*(int(value) for value in sys.argv[1:4]), sys.stdin.read())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass  # Desktop notifications must never interfere with the shell.
