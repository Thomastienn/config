#!/usr/bin/python3
"""Close Quick Settings without grabbing or covering the desktop."""

from contextlib import closing
from pathlib import Path
import select
import subprocess
import sys
import time

from Xlib import X, display, error
from Xlib.ext import ge, xinput


def main():
    window_id = int(sys.argv[1])
    scripts = Path(__file__).resolve().parent
    with closing(display.Display()) as connection:
        root = connection.screen().root
        window = connection.create_resource_object("window", window_id)
        connection.xinput_query_version()
        # Observe only button presses; never grab input or collect keyboard data.
        root.xinput_select_events([(xinput.AllMasterDevices, xinput.RawButtonPressMask)])
        connection.sync()
        next_check = 0
        while True:
            if time.monotonic() >= next_check:
                if window.get_attributes().map_state != X.IsViewable:
                    return
                if connection.get_input_focus().focus != window:
                    break
                try:
                    state = subprocess.run(
                        [sys.argv[2], "-c", str(scripts.parent), "active-windows"],
                        capture_output=True, text=True, timeout=4,
                    )
                except subprocess.TimeoutExpired:
                    break
                if state.returncode or "flyout: flyout" not in state.stdout.splitlines():
                    break
                next_check = time.monotonic() + 0.5
            if connection.pending_events() or select.select([connection], [], [], 0.5)[0]:
                event = connection.next_event()
                if (event.type == ge.GenericEventCode and event.evtype == xinput.RawButtonPress
                        and root.query_pointer().child != window):
                    break
        subprocess.run([str(scripts / "qs.sh"), "watch-close", str(window_id)], timeout=15)


if __name__ == "__main__":
    try:
        main()
    except error.BadWindow:
        pass  # The panel closed while its watcher was checking it.
