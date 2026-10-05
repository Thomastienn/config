#!/usr/bin/env python3
"""Stream home directories into Rofi and open the selection in Nemo."""

import html
from collections import deque
import os
from pathlib import Path
import subprocess
import sys


def scan_command():
    return [sys.executable, "-u", str(Path(__file__).resolve()), "--scan"]


def scan_folders():
    excluded = {"node_modules", "target", "venv", "__pycache__", "build", "dist"}
    pending = deque([Path(".")])
    print("~/")
    while pending:
        parent = pending.popleft()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    path = parent / entry.name
                    # ponytail: one path per menu line; encode labels if newline names are needed.
                    if entry.name.startswith(".") or entry.name in excluded or "\n" in entry.name or path == Path("go/pkg"):
                        continue
                    try:
                        if entry.is_dir():
                            print("~/" + str(path))
                            if not entry.is_symlink():
                                pending.append(path)
                    except OSError:
                        continue
        except OSError:
            continue


def main():
    home = Path.home()
    scan = subprocess.Popen(scan_command(), cwd=home, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    try:
        choice = subprocess.run(
            ["rofi", "-dmenu", "-i", "-matching", "fuzzy", "-sort", "-no-custom",
             "-async-pre-read", "0", "-format", "s", "-theme-str",
             'entry { placeholder: "Open folder in Nemo…"; }'],
            stdin=scan.stdout, capture_output=True, text=True,
        )
    finally:
        scan.stdout.close()
        if scan.poll() is None:
            scan.terminate()
        try:
            scan.wait(timeout=1)
        except subprocess.TimeoutExpired:
            scan.kill()
            scan.wait()
    if choice.returncode == 1:
        return
    if choice.returncode != 0:
        raise RuntimeError(choice.stderr.strip() or f"Rofi exited with status {choice.returncode}.")
    selected = choice.stdout.removesuffix("\n")
    if not selected:
        return
    if not selected.startswith("~/") or ".." in Path(selected[2:]).parts:
        raise RuntimeError("Invalid folder selection.")
    folder = home / selected[2:]
    if not folder.is_dir():
        raise RuntimeError(f"Folder no longer exists: {folder}")
    subprocess.Popen(["nemo", str(folder)], start_new_session=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--scan"]:
            scan_folders()
        else:
            main()
    except BrokenPipeError:
        pass
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Folder finder failed",
                        html.escape(str(error))])
