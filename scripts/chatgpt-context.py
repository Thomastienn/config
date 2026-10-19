#!/usr/bin/env python3
"""Paste selected text or a screenshot into the existing Firefox ChatGPT draft."""

import argparse
import fcntl
import html
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

import dbus
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib
import pyatspi


ACCESS_ERRORS = (GLib.Error, dbus.DBusException, NotImplementedError, LookupError)


def capture(action):
    if action == "selection":
        result = subprocess.run(
            ["xclip", "-selection", "primary", "-target", "UTF8_STRING", "-out"],
            capture_output=True, timeout=3,
        )
        if result.returncode or not result.stdout.decode("utf-8").strip():
            raise RuntimeError("Highlight some text first. The regular clipboard is not used as a fallback.")
        return result.stdout
    args = ["flameshot", "gui", "--raw", "--accept-on-select"] if action == "region" else ["flameshot", "screen", "--raw"]
    result = subprocess.run(args, capture_output=True)
    if action == "region" and not result.stdout and result.returncode in (0, 1):
        return None
    if result.returncode or not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Screenshot capture failed.")
    return result.stdout


def clipboard(data, image=False):
    subprocess.run(
        ["xclip", "-selection", "clipboard", "-target", "image/png" if image else "UTF8_STRING", "-in"],
        input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=3,
        start_new_session=True,
    )


def active_window():
    return int(subprocess.check_output(["xdotool", "getactivewindow"], text=True, timeout=2).strip())


def nodes(root):
    pending = [root]
    while pending:
        node = pending.pop()
        if node is None:
            continue
        yield node
        try:
            pending.extend(list(node))
        except ACCESS_ERRORS:
            continue


def is_chatgpt(document):
    try:
        url = urlsplit(document.queryDocument().getAttributeValue("DocURL"))
        return url.scheme == "https" and url.hostname == "chatgpt.com" and url.port in (None, 443)
    except (*ACCESS_ERRORS, ValueError):
        return False


def dispatch_events():
    # AT-SPI caches focus changes until its D-Bus events are dispatched.
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


def find_composer():
    dispatch_events()
    for app in pyatspi.Registry.getDesktop(0):
        try:
            if app.name.lower() != "firefox":
                continue
            for frame in app:
                if not frame.getState().contains(pyatspi.STATE_ACTIVE):
                    continue
                for document in nodes(frame):
                    if document.getRole() != pyatspi.ROLE_DOCUMENT_WEB:
                        continue
                    if not is_chatgpt(document):
                        continue
                    entries = []
                    pending = [document]
                    while pending:
                        node = pending.pop()
                        if node is None:
                            continue
                        # Do not target controls in embedded documents belonging to another origin.
                        if node != document and node.getRole() == pyatspi.ROLE_DOCUMENT_WEB:
                            continue
                        if node.getRole() == pyatspi.ROLE_ENTRY:
                            state = node.getState()
                            attributes = dict(item.split(":", 1) for item in node.getAttributes() if ":" in item)
                            # shortcut: ChatGPT uses ProseMirror; update this locator if its editor changes.
                            if "ProseMirror" in attributes.get("class", "").split() and all(state.contains(flag) for flag in (
                                pyatspi.STATE_EDITABLE, pyatspi.STATE_MULTI_LINE, pyatspi.STATE_SHOWING,
                            )):
                                entries.append(node)
                        pending.extend(list(node))
                    if len(entries) == 1:
                        return document, entries[0]
        except ACCESS_ERRORS:
            continue
    return None


def focus_composer(window, document, composer):
    if active_window() != window or not is_chatgpt(document):
        raise RuntimeError("Firefox changed focus or page. Paste cancelled; captured context is on the clipboard.")
    if not composer.queryComponent().grabFocus():
        raise RuntimeError("Cannot focus ChatGPT's prompt. Captured context is on the clipboard.")
    text = composer.queryText()
    placeholder = False
    if composer.childCount == 1:
        attributes = dict(item.split(":", 1) for item in composer[0].getAttributes() if ":" in item)
        placeholder = "placeholder" in attributes.get("class", "").split()
    for index in reversed(range(text.getNSelections())):
        text.removeSelection(index)
    if not text.setCaretOffset(text.characterCount):
        raise RuntimeError("Cannot move to the end of the draft. Captured context is on the clipboard.")
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        dispatch_events()
        if active_window() != window:
            break
        if composer.getState().contains(pyatspi.STATE_FOCUSED):
            return 0 if placeholder else text.characterCount
        time.sleep(0.03)
    raise RuntimeError("ChatGPT's prompt is not focused. Captured context is on the clipboard.")


def handoff(data, image):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("dropdown-browser.py")), "--show"],
        capture_output=True, text=True, check=True, timeout=12,
    )
    if not result.stdout.strip():
        raise RuntimeError("Firefox is busy. Captured context is on the clipboard; try again.")
    window = int(result.stdout.strip())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        found = find_composer()
        if found:
            document, composer = found
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Open a ready ChatGPT chat in Mod+G Firefox. Captured context is on the clipboard.")
    length = focus_composer(window, document, composer)
    if not image:
        clipboard((b"\n\n" if length else b"") + data + b"\n\n")
    if active_window() != window or not is_chatgpt(document) or not composer.getState().contains(pyatspi.STATE_FOCUSED):
        raise RuntimeError("Focus changed. Paste cancelled; captured context is on the clipboard.")
    subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=True, timeout=3)


def timeout(_signum, _frame):
    raise RuntimeError("ChatGPT handoff timed out. Captured context is on the clipboard.")


def main(action):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    with (runtime / "chatgpt-context.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        data = capture(action)
        if data is None:
            return
        image = action != "selection"
        clipboard(data, image)
        Atspi.set_timeout(300, 1000)
        signal.signal(signal.SIGALRM, timeout)
        signal.alarm(20)
        try:
            handoff(data, image)
        finally:
            signal.alarm(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selection", "region", "screen"))
    args = parser.parse_args()
    try:
        main(args.action)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, *ACCESS_ERRORS) as error:
        subprocess.run(["notify-send", "-u", "critical", "ChatGPT context failed", html.escape(str(error))])
        raise SystemExit(1)
