#!/usr/bin/env python3
"""Eww audio, gentle focus sessions, saved thoughts, and notification history."""

import html
from datetime import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import afk
import focus_progress as garden


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
    descriptor, temporary = tempfile.mkstemp(prefix=".focus-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(data, output)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def focus_path():
    return afk.directory() / "focus.json"


def guard_path():
    return afk.directory() / "focus-guard.json"


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
    remaining = max(0, math.ceil(state.get("deadline", 0) - time.monotonic()))
    active = state.get("mode") in ("focus", "break")
    return {"active": active, "mode": state.get("mode", "idle"),
            "task": state.get("task", ""), "minutes": state.get("minutes", 10),
            "remaining": f"{remaining // 60:02d}:{remaining % 60:02d}" if active else "",
            "label": ("Break" if state.get("mode") == "break" else "Focus") + f" {remaining // 60:02d}:{remaining % 60:02d}" if active else "Focus"}


def eww(*args):
    executable = shutil.which("eww") or str(Path.home() / "eww/target/release/eww")
    config = os.environ.get("EWW_CONFIG_DIR", str(Path(__file__).resolve().parents[1] / "eww"))
    return capture([executable, "-c", config, *args])


def focus_panel_status():
    state = read_json(focus_path(), {})
    try:
        result = garden.summary(garden.load(), show_bloom=state.get("mode") in ("done", "idle"))
    except (OSError, ValueError) as error:
        result = garden.summary(garden.defaults())
        result["error"] = str(error)
    result.update(focus_status())
    result["feedback"] = state.get("feedback", "")
    guard = read_json(guard_path(), {})
    result["guard"] = ""
    if result["mode"] == "focus" and guard.get("id") == state.get("id"):
        result["guard"] = (f'{guard["status"]} · {guard["nudges"]} {"nudge" if guard["nudges"] == 1 else "nudges"}'
                           f' · {guard["drift"] // 60} min drift')
    result["can_check_in"] = bool(state.get("credited") and state.get("session_mode") == "focus"
                                  and any(item["id"] == state.get("id") for item in result["history"]))
    result["win"] = next((item["win"] for item in result["history"] if item["id"] == state.get("id")), "")
    result["notes"] = read_json(notes_path(), [])[-20:]
    result["reminder_schedule"] = ", ".join(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[day - 1]
                                          for day in result["reminder"]["days"]) + " at " + result["reminder"]["time"]
    return result


def refresh_focus(force=False):
    def display_text(value):
        # Eww unescapes label text once more after decoding JSON.
        if isinstance(value, str):
            return value.replace("\\", "\\\\")
        if isinstance(value, list):
            return [display_text(item) for item in value]
        if isinstance(value, dict):
            return {key: display_text(item) for key, item in value.items()}
        return value

    try:
        opened = any(line.startswith("focus:") for line in eww("active-windows").splitlines())
        if force or opened:
            eww("update", "focus=" + json.dumps(display_text(focus_panel_status())))
        return opened
    except (OSError, subprocess.SubprocessError):
        return False


def update_focus_bar():
    afk.update_bar("focus", focus_status()["label"])
    return True


def focus_reset(done=False):
    state = read_json(focus_path(), {})
    if not state:
        return
    try:
        if state.get("mode") in ("focus", "break"):
            state["session_mode"] = state["mode"]
            state["mode"] = "done" if done else "idle"
            same_boot = state.get("boot") == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            state["elapsed"] = max(0, min(state["minutes"] * 60,
                                         int(time.monotonic() - state.get("started", time.monotonic())))) if same_boot else 0
            state["ended_at"] = datetime.now().astimezone().isoformat()
            guard = read_json(guard_path(), {})
            if guard.get("id") == state.get("id"):
                state["drift"] = int(guard.get("drift", 0))
                state["cheer"] = str(guard.get("cheer", ""))[:90]
                if guard.get("hidden"):
                    subprocess.run([sys.executable, str(Path(__file__).with_name("focus_guard.py")), "restore"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            write_json(focus_path(), state)
        if not state.get("credited"):
            reward = garden.credit(state)
            state["credited"] = True
            if reward:
                seconds = reward["seconds"]
                message = (state.get("cheer", "") + f' {seconds // 60}m {seconds % 60:02d}s of '
                           f'{state["track"].title().lower()} saved.').strip()
                if reward["drift"]:
                    message += f' {100 * seconds // (seconds + reward["drift"])}% focused; drift does not grow the garden.'
                if reward["plants"]:
                    message += " A new plant bloomed!"
                if reward["milestones"]:
                    message += " " + " · ".join(reward["milestones"])
                state["feedback"] = message
            elif state.get("session_mode") == "break":
                state["feedback"] = "Break finished. Ready for one small step?" if done else "Break stopped. Your garden is safe."
            write_json(focus_path(), state)
    finally:
        # Progress/IPC failures must never leave notifications paused.
        try:
            if "pause_set" in state:
                current = int(capture(["dunstctl", "get-pause-level"]))
                if current == state["pause_set"]:
                    capture(["dunstctl", "set-pause-level", str(state["pause_before"])])
                state.pop("pause_set", None)
                state.pop("pause_before", None)
                write_json(focus_path(), state)
        finally:
            afk.update_bar("focus", "Focus")
            refresh_focus()


def focus_start(minutes, mode="focus", ask=False):
    if minutes not in (5, 10, 25) or mode not in ("focus", "break"):
        raise ValueError("Choose a 5, 10, or 25 minute session.")
    previous = read_json(focus_path(), {})
    data = garden.load()
    task = data["actions"][data["track"]]
    if ask:
        task = prompt("One tiny next action…", task)
        if task is None:
            return
    capture(["systemctl", "--user", "stop", "thomas-focus.service"])
    focus_reset()
    started = time.monotonic()
    write_json(focus_path(), {"id": str(uuid4()), "track": data["track"],
                              "date": datetime.now().astimezone().date().isoformat(),
                              "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                              "started": started, "mode": mode, "task": task or "One small step", "minutes": minutes,
                              "focus_minutes": minutes if mode == "focus" else previous.get("focus_minutes", 10),
                              "deadline": started + minutes * 60})
    try:
        capture(["systemctl", "--user", "start", "thomas-focus.service"])
    except (OSError, subprocess.SubprocessError):
        focus_reset()
        raise
    refresh_focus()


def focus_run():
    from gi.repository import Gio, GLib

    state = read_json(focus_path(), {})
    if state.get("mode") not in ("focus", "break"):
        raise RuntimeError("Start a focus session from Eww first.")
    loop = GLib.MainLoop()
    finished = False
    stopped = False

    def complete():
        nonlocal finished
        finished = True
        loop.quit()
        return False

    def stop(*_):
        nonlocal stopped
        stopped = True
        loop.quit()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    display = None
    display_watch = None
    guard = None
    timers = []

    def display_closed(_pid, status):
        nonlocal display_watch
        display_watch = None
        display.returncode = os.waitstatus_to_exitcode(status)
        stop()

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                             "PrepareForSleep", "/org/freedesktop/login1", None,
                             Gio.DBusSignalFlags.NONE, lambda *_: stop())
        bus.connect("closed", stop)
        display = subprocess.Popen(["xprop", "-root", "-spy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        display_watch = GLib.child_watch_add(display.pid, display_closed)
        if state["mode"] == "focus":
            state["pause_before"] = int(capture(["dunstctl", "get-pause-level"]))
            state["pause_set"] = max(50, state["pause_before"])
            write_json(focus_path(), state)
            capture(["dunstctl", "set-pause-level", str(state["pause_set"])])
            python = Path.home() / ".virtualenvs/focus-guard/bin/python"
            guard = subprocess.Popen([str(python if python.exists() else sys.executable),
                                      str(Path(__file__).with_name("focus_guard.py"))], stdout=subprocess.DEVNULL)
        update_focus_bar()
        refresh_focus()
        timers.append(GLib.timeout_add_seconds(1, update_focus_bar))
        timers.append(GLib.timeout_add(max(1, math.ceil((state["deadline"] - time.monotonic()) * 1000)), complete))
        if not stopped:
            loop.run()
    finally:
        try:
            if display_watch is not None:
                GLib.source_remove(display_watch)
            # The completion source removes itself when it fires.
            for timer in timers[:1] if finished else timers:
                GLib.source_remove(timer)
            if display is not None and display.poll() is None:
                display.terminate()
                display.wait(timeout=2)
            if guard is not None and guard.poll() is None:
                guard.terminate()
                guard.wait(timeout=10)
        finally:
            focus_reset(done=finished)
    if finished and not refresh_focus():
        terminal = read_json(focus_path(), {})
        notify("Break finished" if state["mode"] == "break" else "Small session finished",
               terminal.get("feedback", "Continue or take a break. Your garden is safe."))


def focus_edit(kind):
    data = garden.load()
    state = read_json(focus_path(), {})
    track = state.get("track", data["track"]) if focus_status()["active"] else data["track"]
    if kind == "action":
        question, previous = "Next tiny action for " + track + "…", data["actions"][track]
    elif kind == "win":
        if not state.get("credited") or state.get("session_mode") != "focus":
            return
        question = "Explain one idea from memory, then check notes…" if state["track"] == "study" else "What changed or what did you learn?"
        previous = next((item["win"] for item in data["sessions"] if item["id"] == state.get("id")), "")
    else:
        raise ValueError("Unknown focus note.")
    try:
        answer = prompt(question, previous)
        if answer is not None:
            with garden.edit() as data:
                if kind == "action":
                    data["actions"][track] = answer
                else:
                    for item in data["sessions"]:
                        if item["id"] == state["id"]:
                            item["win"] = answer
    finally:
        subprocess.run([str(Path(__file__).resolve().parents[1] / "eww/scripts/qs.sh"), "focus-open"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def configure_reminder(enabled):
    if not enabled:
        capture(["systemctl", "--user", "disable", "--now", "thomas-focus-reminder.timer"])
        with garden.edit() as data:
            data["reminder"]["enabled"] = False
        refresh_focus()
        return
    data = garden.load()
    names = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    try:
        selected = prompt("Reminder days: Mon,Tue,Wed…", ",".join(names[day - 1] for day in data["reminder"]["days"]))
        if selected is None:
            return
        tokens = [token.strip().title() for token in selected.split(",")]
        if not tokens or any(token not in names for token in tokens):
            raise ValueError("Use day names separated by commas, for example Mon,Wed,Fri.")
        days = sorted({names.index(token) + 1 for token in tokens})
        selected_time = prompt("Reminder local time: HH:MM (24 hour)", data["reminder"]["time"])
        if selected_time is None:
            return
        try:
            selected_time = datetime.strptime(selected_time, "%H:%M").strftime("%H:%M")
        except ValueError:
            raise ValueError("Use a 24-hour time, for example 18:30.") from None
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user/thomas-focus-reminder.timer.d"
        schedule = ",".join(names[day - 1] for day in days) + " *-*-* " + selected_time + ":00"
        root.mkdir(parents=True, exist_ok=True)
        (root / "schedule.conf").write_text("[Timer]\nOnCalendar=\nOnCalendar=" + schedule + "\n")
        capture(["systemctl", "--user", "daemon-reload"])
        capture(["systemctl", "--user", "enable", "--now", "thomas-focus-reminder.timer"])
        capture(["systemctl", "--user", "restart", "thomas-focus-reminder.timer"])
        with garden.edit() as data:
            data["reminder"].update(enabled=True, days=days, time=selected_time)
    finally:
        subprocess.run([str(Path(__file__).resolve().parents[1] / "eww/scripts/qs.sh"), "focus-open", "2"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def focus_remind():
    now = datetime.now().astimezone()
    today = now.date().isoformat()
    data = garden.load()
    reminder = data["reminder"]
    if (not reminder["enabled"] or now.isoweekday() not in reminder["days"]
            or now.strftime("%H:%M") != reminder["time"] or reminder["last_date"] == today
            or focus_status()["active"] or garden.day_totals(data).get(today, 0) >= 300):
        return
    # Fail closed if session/lock/DND state cannot be established.
    try:
        session = os.environ.get("XDG_SESSION_ID") or capture(["loginctl", "show-user", str(os.getuid()), "-p", "Display", "--value"])
        if not session or capture(["loginctl", "show-session", session, "-p", "LockedHint", "--value"]) != "no":
            return
        locked = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "i3lock"], stdout=subprocess.DEVNULL, timeout=2)
        if locked.returncode != 1 or int(capture(["dunstctl", "get-pause-level"])) > 0:
            return
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    with garden.edit() as data:
        if data["reminder"]["last_date"] == today:
            return
        data["reminder"]["last_date"] = today
    capture(["notify-send", "-a", "Focus reminder", "-t", "60000", "One small step?",
             "Five minutes is enough to begin. Open Focus when you are ready."])


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
    elif action == "focus-live":
        print(json.dumps(focus_status()))
    elif action == "focus-refresh":
        refresh_focus(force=True)
    elif action == "focus-track" and len(args) == 2:
        if args[1] not in garden.TRACKS:
            raise ValueError("Choose Study or Coding.")
        if focus_status()["active"]:
            raise ValueError("Finish or stop this session before switching tracks.")
        with garden.edit() as data:
            data["track"] = args[1]
        refresh_focus()
    elif action == "focus-edit" and len(args) == 2:
        focus_edit(args[1])
    elif action == "focus-reminder" and len(args) == 2 and args[1] in ("on", "off"):
        configure_reminder(args[1] == "on")
    elif action == "focus-remind":
        focus_remind()
    elif action == "park":
        reopen = refresh_focus()
        try:
            note = prompt("Save for your next break…")
            if note:
                notes = read_json(notes_path(), [])
                notes.append(note)
                write_json(notes_path(), notes)
        finally:
            if reopen:
                subprocess.run([str(Path(__file__).resolve().parents[1] / "eww/scripts/qs.sh"), "focus-open"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif action == "clear-notes":
        write_json(notes_path(), [])
        refresh_focus()
    elif action == "clear-history":
        capture(["dunstctl", "history-clear"])
    else:
        raise ValueError("Unknown desktop control.")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] in ("focus-start", "focus-continue", "focus-break", "focus-stop",
                                                "focus-track", "focus-edit", "focus-reminder"):
            descriptor = os.open(afk.directory() / "focus-command.lock", os.O_CREAT | os.O_RDWR, 0o600)
            with os.fdopen(descriptor, "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                main(sys.argv[1:])
        else:
            main(sys.argv[1:])
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        try:
            notify("Desktop control failed", str(error), critical=True)
        except (OSError, subprocess.SubprocessError):
            pass
        sys.exit(1)
