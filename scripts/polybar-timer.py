#!/usr/bin/env python3
"""One countdown or stopwatch, with event-driven Polybar output."""

import argparse
import fcntl
import html
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def now():
    # Include suspend time without depending on wall-clock adjustments.
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def directory():
    path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "thomas-polybar-timer"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def read(path):
    try:
        state = json.loads(path.read_text())
        if (state["mode"] in ("countdown", "stopwatch")
                and math.isfinite(state["seconds"]) and state["seconds"] >= 0
                and (state["since"] is None
                     or math.isfinite(state["since"]) and 0 <= state["since"] <= now())):
            return state
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        pass
    return {}


def seconds(state, timestamp):
    elapsed = timestamp - state["since"] if state["since"] is not None else 0
    return max(0, state["seconds"] + (-elapsed if state["mode"] == "countdown" else elapsed))


def notify(title, body, critical=False):
    try:
        subprocess.run(["notify-send", "-a", "Timer", "-u", "critical" if critical else "normal",
                        title, html.escape(body)], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Timer notification failed: {error}", file=sys.stderr)


def change(action=None, minutes=None):
    if action == "countdown" and (minutes is None or not math.isfinite(minutes) or not 0 < minutes <= 1440):
        raise ValueError("Enter minutes greater than zero, up to 1440 (24 hours).")
    root = directory()
    path = root / "state.json"
    finished = False
    with (root / "state.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = read(path)
        state = original.copy()
        timestamp = now()
        if state and state["mode"] == "countdown" and state["since"] is not None and seconds(state, timestamp) == 0:
            state.update(seconds=0, since=None)
            finished = True
        if action in ("countdown", "stopwatch"):
            state = {"mode": action, "seconds": minutes * 60 if action == "countdown" else 0,
                     "since": timestamp}
        elif action == "toggle" and state:
            if state["since"] is not None:
                state.update(seconds=seconds(state, timestamp), since=None)
            elif state["mode"] == "stopwatch" or state["seconds"] > 0:
                state["since"] = timestamp
        elif action == "clear":
            state = {}
        if state != original:
            with tempfile.NamedTemporaryFile(mode="w", dir=root, delete=False) as temporary:
                try:
                    json.dump(state, temporary)
                    temporary.close()
                    os.replace(temporary.name, path)
                finally:
                    Path(temporary.name).unlink(missing_ok=True)
    if finished and action not in ("countdown", "stopwatch", "clear"):
        notify("Timer finished", "Countdown complete. Click the timer to start another.", critical=True)
    return state


def label(state):
    if not state:
        return ""
    value = seconds(state, now())
    if state["mode"] == "countdown" and value == 0:
        return "%{F#DBA0AA} Done%{F-}"
    value = math.ceil(value) if state["mode"] == "countdown" else int(value)
    hours, remainder = divmod(value, 3600)
    minutes, seconds_left = divmod(remainder, 60)
    text = f"{hours}:{minutes:02}:{seconds_left:02}" if hours else f"{minutes:02}:{seconds_left:02}"
    icon = "" if state["mode"] == "countdown" else ""
    if state["since"] is None:
        return f"%{{F#ABAFA4}} {text}%{{F-}}"
    return f"{icon} {text}"


def watch():
    from gi.repository import Gio, GLib

    timer = None
    previous = None

    def refresh(*_):
        nonlocal timer, previous
        state = change()
        text = label(state)
        if text != previous:
            sys.stdout.write(text + "\n")
            sys.stdout.flush()
            previous = text
        if state and state["since"] is not None:
            if timer is None:
                timer = GLib.timeout_add(1000, tick)
        elif timer is not None:
            GLib.source_remove(timer)
            timer = None

    def tick():
        nonlocal timer
        timer = None
        refresh()
        return False

    def changed(_monitor, file, other, _event):
        if any(item and item.get_basename() == "state.json" for item in (file, other)):
            refresh()

    monitor = Gio.File.new_for_path(str(directory())).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
    monitor.connect("changed", changed)
    refresh()
    # shortcut: alerts require a running bar; use a user service if alerts must outlive Polybar.
    GLib.MainLoop().run()


def choose(prompt, options, custom=False):
    result = subprocess.run(["rofi", "-dmenu", "-i", "-p", prompt,
                             *([] if custom else ["-no-custom"]),
                             "-theme-str", "listview { lines: 6; fixed-height: false; }"],
                            input="\n".join(options), capture_output=True, text=True)
    if result.returncode == 1:
        return ""
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not open the timer menu.")
    return result.stdout.strip()


def menu():
    state = change()
    options = ["Countdown…", "Start stopwatch"]
    if state:
        if state["since"] is not None:
            options.append("Pause")
        elif state["mode"] == "stopwatch" or state["seconds"] > 0:
            options.append("Resume")
        options.append("Clear")
    selected = choose("Timer", options)
    if selected == "Countdown…":
        value = choose("Minutes (up to 1440)", ["5", "10", "15", "25", "30", "60"], custom=True)
        if value:
            change("countdown", float(value))
    elif selected == "Start stopwatch":
        change("stopwatch")
    elif selected in ("Pause", "Resume"):
        change("toggle")
    elif selected == "Clear":
        change("clear")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="menu",
                        choices=["menu", "watch", "countdown", "stopwatch", "toggle", "clear"])
    parser.add_argument("minutes", nargs="?", type=float)
    args = parser.parse_args()
    if args.minutes is not None and args.action != "countdown":
        parser.error("minutes are only used with countdown")
    if args.action == "menu":
        menu()
    elif args.action == "watch":
        watch()
    else:
        change(args.action, args.minutes)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        notify("Timer failed", str(error), critical=True)
        sys.exit(1)
