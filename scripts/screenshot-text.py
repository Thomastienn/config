#!/usr/bin/env python3
"""Recognize a selected screen region only when invoked."""

import html
import subprocess


def main():
    capture = subprocess.run(["flameshot", "gui", "--raw", "--accept-on-select"],
                             capture_output=True)
    if not capture.stdout:
        if capture.returncode not in (0, 1):
            raise RuntimeError(capture.stderr.decode(errors="replace").strip() or "Capture failed.")
        return
    capture.check_returncode()
    recognized = subprocess.run(
        ["/home/linuxbrew/.linuxbrew/bin/tesseract", "stdin", "stdout", "-l", "eng"],
        input=capture.stdout, capture_output=True,
    )
    if recognized.returncode != 0:
        raise RuntimeError(recognized.stderr.decode(errors="replace").strip() or "Recognition failed.")
    text = recognized.stdout.decode("utf-8").strip()
    if not text:
        subprocess.run(["notify-send", "Screenshot text", "No text found. Select a clearer region."], check=True)
        return
    subprocess.run(["xclip", "-selection", "clipboard", "-in"],
                   input=text.encode("utf-8"), check=True)
    subprocess.run(["notify-send", "Screenshot text", "Text copied to clipboard."], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Screenshot text failed",
                        html.escape(str(error))])
