#!/usr/bin/env python3
"""Capture a Taskwarrior task without leaving the current workspace."""

import html
import shlex
import subprocess


def main():
    text = ""
    message = "Example: Read chapter 3 due:fri"
    while True:
        prompt = subprocess.run(
            ["rofi", "-dmenu", "-filter", text, "-mesg", html.escape(message),
             "-theme-str", 'listview { lines: 0; fixed-height: false; } '
             'entry { placeholder: "Add task…"; }'],
            input="", capture_output=True, text=True,
        )
        if prompt.returncode not in (0, 1):
            raise RuntimeError(prompt.stderr.strip() or f"Rofi exited with status {prompt.returncode}.")
        if prompt.returncode != 0 or not prompt.stdout.strip():
            return
        text = prompt.stdout.strip()
        try:
            arguments = shlex.split(text)
            if not arguments or not any(arguments):
                return
            result = subprocess.run(
                ["/home/linuxbrew/.linuxbrew/bin/task", "rc.color=off", "add", *arguments],
                input="", capture_output=True, text=True,
            )
            if result.returncode == 0:
                subprocess.run(["notify-send", "-a", "Taskwarrior", "Task added",
                                html.escape(result.stdout.strip() or text)], check=True)
                return
            message = result.stderr.strip() or result.stdout.strip() or "Could not add task."
        except ValueError as error:
            message = str(error)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Quick task failed", str(error)])
