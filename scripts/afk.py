#!/usr/bin/env python3
"""Lid-aware keep-awake mode, owned by thomas-afk.service."""

import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys


def directory():
    path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "thomas-desktop"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def read_state():
    try:
        data = json.loads((directory() / "afk.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state):
    target = directory() / "afk.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(state))
    temporary.replace(target)


def lid_open():
    lids = list(Path("/proc/acpi/button/lid").glob("*/state"))
    try:
        return bool(lids) and all(re.search(r"\bopen\b", lid.read_text()) for lid in lids)
    except OSError:
        return False


def active():
    state = read_state()
    try:
        if not state.get("active") or int(state.get("pid", 0)) <= 1:
            return False
        os.kill(int(state["pid"]), 0)
        return lid_open()
    except (OSError, ValueError):
        return False


def command(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, timeout=5, check=True, **kwargs).stdout


def update_bar(module, label):
    try:
        subprocess.run(["polybar-msg", "action", module, "send", label],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1, check=True)
    except (OSError, subprocess.SubprocessError):
        # A missing bar must not prevent idle-setting or notification recovery.
        pass


def idle_control(action):
    socket = directory().parent / "thomas-xidlehook.sock"
    command([str(Path.home() / ".cargo/bin/xidlehook-client"), "--socket", str(socket),
             "control", "--action", action])


def snapshot(text):
    screen = re.search(r"timeout:\s*(\d+)\s+cycle:\s*(\d+)", text)
    dpms = re.search(r"Standby:\s*(\d+)\s+Suspend:\s*(\d+)\s+Off:\s*(\d+)", text)
    if not screen:
        raise RuntimeError("Could not read display idle settings; AFK was not enabled.")
    return {"screen": list(map(int, screen.groups())),
            "dpms": list(map(int, dpms.groups())) if dpms else None,
            "dpms_enabled": "DPMS is Enabled" in text,
            "display": os.environ.get("DISPLAY", ""),
            "xauthority": os.environ.get("XAUTHORITY", "")}


def reset():
    state = read_state()
    if not state:
        return
    state["active"] = False
    save(state)
    env = dict(os.environ, DISPLAY=state["display"])
    if state.get("xauthority"):
        env["XAUTHORITY"] = state["xauthority"]
    errors = []
    actions = [lambda: idle_control("Enable"),
               lambda: command([str(Path.home() / ".cargo/bin/xidlehook-client"), "--socket",
                                str(directory().parent / "thomas-xidlehook.sock"), "reset-idle"]),
               lambda: command(["xset", "s", *map(str, state["screen"])], env=env)]
    if state.get("dpms"):
        actions.extend([lambda: command(["xset", "dpms", *map(str, state["dpms"])], env=env),
                        lambda: command(["xset", "+dpms" if state["dpms_enabled"] else "-dpms"], env=env)])
    for action in actions:
        try:
            action()
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    update_bar("afk", "")
    if errors:
        raise RuntimeError("AFK stopped, but idle settings need recovery: " + "; ".join(errors))
    (directory() / "afk.json").unlink(missing_ok=True)


def run():
    from gi.repository import Gio, GLib

    if not lid_open():
        raise RuntimeError("AFK needs an open laptop lid and a readable lid sensor.")
    if read_state():
        reset()
    # Check the control socket before changing any display settings.
    command([str(Path.home() / ".cargo/bin/xidlehook-client"), "--socket",
             str(directory().parent / "thomas-xidlehook.sock"), "query"])
    state = snapshot(command(["xset", "q"]))
    state.update(active=False, pid=os.getpid())
    save(state)
    loop = GLib.MainLoop()

    def stop(*_):
        state["active"] = False
        save(state)
        loop.quit()

    def check_lid():
        if not lid_open() or display_watch.poll() is not None:
            stop()
            return False
        return True

    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                         "PrepareForSleep", "/org/freedesktop/login1", None,
                         Gio.DBusSignalFlags.NONE, lambda *_: stop())
    bus.connect("closed", stop)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # A persistent X client exits when the graphical session closes, including with user lingering.
    display_watch = subprocess.Popen(["xprop", "-root", "-spy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    GLib.timeout_add(500, check_lid)
    try:
        idle_control("Disable")
        command(["xset", "s", "off"])
        if state["dpms"]:
            command(["xset", "-dpms"])
        state["active"] = True
        save(state)
        update_bar("afk", "AFK")
        loop.run()
    finally:
        try:
            if display_watch.poll() is None:
                display_watch.terminate()
            display_watch.wait(timeout=3)
        finally:
            reset()


def toggle():
    if active():
        command(["systemctl", "--user", "stop", "thomas-afk.service"])
        return
    if not lid_open():
        raise RuntimeError("Open the laptop lid before enabling AFK.")
    socket = directory().parent / "thomas-xidlehook.sock"
    if not socket.is_socket():
        raise RuntimeError("Restart i3 once to enable the new idle controls, then try AFK again.")
    command(["systemctl", "--user", "import-environment", "DISPLAY", "XAUTHORITY"])
    command(["systemctl", "--user", "start", "thomas-afk.service"])


if __name__ == "__main__":
    try:
        action = sys.argv[1] if len(sys.argv) > 1 else "status"
        if action == "run":
            run()
        elif action == "reset":
            reset()
        elif action == "toggle":
            toggle()
        elif action == "bar":
            print("AFK" if active() else "", flush=True)
        elif action == "status":
            print(json.dumps(active()))
        else:
            raise ValueError("Unknown AFK action.")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        if len(sys.argv) > 1 and sys.argv[1] in ("toggle", "run"):
            subprocess.run(["notify-send", "-u", "critical", "AFK could not change", html.escape(str(error))], timeout=5)
        sys.exit(1)
