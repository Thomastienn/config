#!/usr/bin/env python3
"""Open SSH in the same main tmux terminal used by the folder launcher."""

import html
import json
from pathlib import Path
import runpy
import subprocess
import sys


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("Select one SSH host in Rofi.")
    host = sys.argv[1]
    launcher = runpy.run_path(str(Path(__file__).with_name("project-launcher.py")))
    container, session = launcher["main_terminal"]()
    command = '/usr/bin/ssh -- "$1"; status=$?; if [ "$status" -ne 0 ]; then ' \
              'printf "\\nSSH exited (%s). Press Enter to close.\\n" "$status"; ' \
              'read -r reply; fi; exit "$status"'
    subprocess.run([launcher["TMUX"], "new-window", "-t", session,
                    "-n", f"ssh:{host}", "/bin/sh", "-c", command, "ssh", host], check=True)
    focus = subprocess.run(["i3-msg", f"[con_id={container}] focus"],
                           capture_output=True, text=True, check=True)
    if not all(result.get("success") for result in json.loads(focus.stdout)):
        raise RuntimeError("SSH tab created, but could not focus the main terminal.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "SSH launcher failed",
                        html.escape(str(error))])
