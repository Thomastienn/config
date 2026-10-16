#!/usr/bin/env python3
"""Eww audio, gentle focus sessions, saved thoughts, and notification history."""

import html
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import afk


def capture(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=5).stdout.strip()


def read_json(path, default):
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.replace(path)


def focus_path():
    return afk.directory() / "focus.json"


def notes_path():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "thomas-desktop/focus-notes.json"


def notify(title, body="", critical=False):
    capture(["notify-send", "-a", "Focus", "-u", "critical" if critical else "normal",
             title, html.escape(body)])


def prompt(placeholder, previous=""):
    subprocess.run([str(Path(__file__).resolve().parents[1] / "eww/scripts/qs.sh"), "close"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = subprocess.run(["rofi", "-dmenu", "-filter", previous, "-format", "f", "-theme-str",
                             'listview { lines: 0; } entry { placeholder: "' + placeholder + '"; }'],
                            input="", capture_output=True, text=True)
    if result.returncode == 1:
        return None
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Focus prompt failed.")
    return result.stdout.strip()[:300]


def audio_devices():
    sinks = json.loads(capture(["pactl", "-f", "json", "list", "sinks"]))
    sources = json.loads(capture(["pactl", "-f", "json", "list", "sources"]))
    return sinks, [source for source in sources if not source["name"].endswith(".monitor")
                   and source.get("properties", {}).get("device.class") != "monitor"]


def switch_audio(kind, index):
    if kind not in ("output", "input"):
        raise ValueError("Unknown audio device type.")
    sinks, sources = audio_devices()
    devices = sinks if kind == "output" else sources
    device = next((item for item in devices if item["index"] == index), None)
    if device is None:
        raise RuntimeError("Audio device disconnected. Open the device list again.")
    suffix = "sink" if kind == "output" else "source"
    capture(["pactl", f"set-default-{suffix}", device["name"]])
    stream_type = "sink-inputs" if kind == "output" else "source-outputs"
    streams = json.loads(capture(["pactl", "-f", "json", "list", stream_type]))
    real_sources = {item["index"] for item in sources}
    for stream in streams:
        # Preserve desktop-audio recordings when switching the microphone.
        if kind == "input" and stream.get("source") not in real_sources:
            continue
        try:
            capture(["pactl", f"move-{stream_type[:-1]}", str(stream["index"]), device["name"]])
        except subprocess.CalledProcessError:
            remaining = json.loads(capture(["pactl", "-f", "json", "list", stream_type]))
            if any(item["index"] == stream["index"] for item in remaining):
                raise RuntimeError("Default device changed, but an active audio stream could not move.")


def history():
    data = json.loads(capture(["dunstctl", "history"]))
    items = data.get("data", [[]])[0]
    result = []
    for item in reversed(items):
        def value(key):
            field = item.get(key, "")
            return str(field.get("data", "") if isinstance(field, dict) else field)
        result.append({"summary": value("summary"), "body": value("body"), "app": value("appname")})
    return result[:30]


def focus_status():
    state = read_json(focus_path(), {})
    remaining = max(0, int(state.get("deadline", 0) - time.monotonic()))
    active = state.get("mode") in ("focus", "break")
    return {"active": active, "mode": state.get("mode", "idle"),
            "task": state.get("task", ""), "minutes": state.get("minutes", 10),
            "remaining": f"{remaining // 60:02d}:{remaining % 60:02d}" if active else "",
            "label": ("Break" if state.get("mode") == "break" else "Focus") + f" {remaining // 60:02d}:{remaining % 60:02d}" if active else ""}


def update_focus_bar():
    afk.update_bar("focus", focus_status()["label"])
    return True


def focus_reset(done=False):
    state = read_json(focus_path(), {})
    if not state:
        return
    state["mode"] = "done" if done else "idle"
    write_json(focus_path(), state)
    afk.update_bar("focus", "")
    if "pause_set" in state:
        current = int(capture(["dunstctl", "get-pause-level"]))
        if current == state["pause_set"]:
            capture(["dunstctl", "set-pause-level", str(state["pause_before"])])
        state.pop("pause_set", None)
        state.pop("pause_before", None)
    write_json(focus_path(), state)


def focus_start(minutes, mode="focus", ask=True):
    if minutes not in (5, 10, 25) or mode not in ("focus", "break"):
        raise ValueError("Choose a 5, 10, or 25 minute session.")
    previous = read_json(focus_path(), {})
    task = previous.get("task", "")
    if ask:
        task = prompt("One tiny next action…", task)
        if task is None:
            return
    capture(["systemctl", "--user", "stop", "thomas-focus.service"])
    write_json(focus_path(), {"mode": mode, "task": task or "One small step", "minutes": minutes,
                              "focus_minutes": minutes if mode == "focus" else previous.get("focus_minutes", 10),
                              "deadline": time.monotonic() + minutes * 60})
    capture(["systemctl", "--user", "start", "thomas-focus.service"])


def focus_run():
    from gi.repository import Gio, GLib

    state = read_json(focus_path(), {})
    if state.get("mode") not in ("focus", "break"):
        raise RuntimeError("Start a focus session from Eww first.")
    loop = GLib.MainLoop()
    finished = False

    def complete():
        nonlocal finished
        finished = True
        loop.quit()
        return False

    def stop(*_):
        loop.quit()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                         "PrepareForSleep", "/org/freedesktop/login1", None,
                         Gio.DBusSignalFlags.NONE, lambda *_: stop())
    bus.connect("closed", stop)
    try:
        if state["mode"] == "focus":
            state["pause_before"] = int(capture(["dunstctl", "get-pause-level"]))
            state["pause_set"] = max(50, state["pause_before"])
            write_json(focus_path(), state)
            capture(["dunstctl", "set-pause-level", str(state["pause_set"])])
        update_focus_bar()
        GLib.timeout_add_seconds(1, update_focus_bar)
        GLib.timeout_add(max(1, int((state["deadline"] - time.monotonic()) * 1000)), complete)
        loop.run()
    finally:
        focus_reset(done=finished)
    if finished:
        notify("Break finished" if state["mode"] == "break" else "Small session finished",
               "Continue, take a break, or stop. Your saved thoughts are in Eww.")


def status():
    result = {"outputs": [], "inputs": [], "audio_available": False, "audio_error": "Audio unavailable",
              "focus": focus_status(), "afk": afk.active(),
              "notes": read_json(notes_path(), []), "notifications": [], "history_available": False}
    try:
        sinks, sources = audio_devices()
        for key, devices, default_command in (("outputs", sinks, "get-default-sink"),
                                               ("inputs", sources, "get-default-source")):
            default = capture(["pactl", default_command])
            result[key] = [{"id": int(device["index"]), "name": device.get("description") or device["name"],
                            "selected": device["name"] == default} for device in devices]
        result.update(audio_available=True, audio_error="")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        pass
    try:
        result["notifications"] = history()
        result["history_available"] = True
    except (OSError, ValueError, IndexError, TypeError, subprocess.SubprocessError):
        pass
    result["note_count"] = len(result["notes"])
    result["notes"] = result["notes"][-20:]
    return result


def main(args):
    action = args[0] if args else "status"
    if action == "status":
        print(json.dumps(status()))
    elif action == "audio" and len(args) == 3:
        switch_audio(args[1], int(args[2]))
    elif action == "focus-start":
        focus_start(int(args[1]))
    elif action == "focus-continue":
        focus_start(int(read_json(focus_path(), {}).get("focus_minutes", 10)), ask=False)
    elif action == "focus-break":
        focus_start(5, "break", ask=False)
    elif action == "focus-stop":
        capture(["systemctl", "--user", "stop", "thomas-focus.service"])
    elif action == "focus-run":
        focus_run()
    elif action == "focus-reset":
        state = read_json(focus_path(), {})
        focus_reset(done=state.get("mode") == "done")
    elif action == "focus-bar":
        print(focus_status()["label"])
    elif action == "park":
        note = prompt("Save for your next break…")
        if note:
            notes = read_json(notes_path(), [])
            notes.append(note)
            write_json(notes_path(), notes)
    elif action == "clear-notes":
        write_json(notes_path(), [])
    elif action == "clear-history":
        capture(["dunstctl", "history-clear"])
    else:
        raise ValueError("Unknown desktop control.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        try:
            notify("Desktop control failed", str(error), critical=True)
        except (OSError, subprocess.SubprocessError):
            pass
        sys.exit(1)
