#!/usr/bin/env python3
"""Eww audio device routing, notification history and do not disturb."""

import fcntl
import html
import json
import subprocess
import sys

import afk

DND_RULE = "do-not-disturb"


def capture(args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=5).stdout.strip()


def notify(title, body="", critical=False):
    capture(["notify-send", "-a", "Desktop", "-u", "critical" if critical else "normal",
             title, html.escape(body)])


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


def dnd_enabled():
    data = json.loads(capture(["dunstctl", "rules", "--json"]))
    for rule in data["data"][0]:
        if rule["name"]["data"] == DND_RULE:
            enabled = rule["enabled"]["data"]
            if type(enabled) is bool:
                return enabled
            break
    raise ValueError("Do not disturb unavailable. Reload Dunst notification rules.")


def toggle_dnd():
    # Serialize clicks so an earlier enable cannot dismiss notifications after disable.
    with (afk.directory() / "dnd.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        dnd_enabled()
        capture(["dunstctl", "rule", DND_RULE, "toggle"])
        if dnd_enabled():
            capture(["dunstctl", "close-all"])


def status():
    result = {"outputs": [], "inputs": [], "audio_available": False, "audio_error": "Audio unavailable",
              "afk": afk.active(), "dnd": False, "dnd_available": False,
              "notifications": [], "history_available": False}
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
        result["dnd"] = dnd_enabled()
        result["dnd_available"] = True
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError):
        pass
    try:
        result["notifications"] = history()
        result["history_available"] = True
    except (OSError, ValueError, IndexError, TypeError, subprocess.SubprocessError):
        pass
    return result


def main(args):
    action = args[0] if args else "status"
    if action == "status":
        print(json.dumps(status()))
    elif action == "audio" and len(args) == 3:
        switch_audio(args[1], int(args[2]))
    elif action == "clear-history":
        capture(["dunstctl", "history-clear"])
    elif action == "dnd" and len(args) == 1:
        toggle_dnd()
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
