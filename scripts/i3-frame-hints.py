#!/usr/bin/env python3
"""Tell Picom which i3 client frames join a separate tab or stack header."""

import fcntl
import os
from pathlib import Path

from Xlib import X, Xatom, display, error


def update_hints(connection, previous):
    atom = connection.intern_atom("_THOMAS_I3_TAB_BODY")
    current = {}
    for frame in connection.screen().root.query_tree().children:
        try:
            if frame.get_wm_class() != ("i3-frame", "i3-frame"):
                continue
            frame.change_attributes(event_mask=X.SubstructureNotifyMask)
            for client in frame.query_tree().children:
                # A zero top inset means i3 paints the header in another frame.
                joined = int(client.get_geometry().y == 0)
                current[client.id] = joined
                if previous.get(client.id) != joined:
                    client.change_property(atom, Xatom.CARDINAL, 32, [joined])
        except (error.BadWindow, error.BadDrawable):
            continue
    connection.sync()
    return current


def main():
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    with (runtime / "thomas-i3-frame-hints.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        connection = display.Display()
        connection.screen().root.change_attributes(event_mask=X.SubstructureNotifyMask)
        previous = update_hints(connection, {})
        changes = (X.CreateNotify, X.MapNotify, X.ReparentNotify,
                   X.ConfigureNotify, X.DestroyNotify)
        try:
            while True:
                event = connection.next_event()
                if event.type in changes:
                    previous = update_hints(connection, previous)
        finally:
            connection.close()


if __name__ == "__main__":
    main()
