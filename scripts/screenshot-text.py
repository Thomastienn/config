#!/usr/bin/env python3
"""Recognize a selected screen region only when invoked; --accurate uses a local vision model."""

import base64
import html
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

BREW = "/home/linuxbrew/.linuxbrew/bin"
MODEL = "qwen3-vl:4b-instruct"  # Pulled by setup/hermes.py; the -instruct tag skips slow thinking.
PROMPT = ("Transcribe all text in this image exactly as it appears. Preserve line breaks. "
          "Output only the text: no commentary, no markdown, no code fences.")


def tesseract(image):
    # Screen text is ~96 DPI; Tesseract wants ~300 DPI and dark text on a light background.
    mean = subprocess.run([f"{BREW}/magick", "-", "-colorspace", "Gray", "-format", "%[fx:mean]", "info:"],
                          input=image, capture_output=True, check=True).stdout
    prepared = subprocess.run([f"{BREW}/magick", "-", "-colorspace", "Gray",
                               *(["-negate"] if float(mean) < 0.5 else []), "-resize", "300%", "png:-"],
                              input=image, capture_output=True, check=True).stdout
    recognized = subprocess.run(
        [f"{BREW}/tesseract", "stdin", "stdout", "--tessdata-dir", str(Path.home() / ".local/share/tessdata"),
         "-l", "eng", "--psm", "6", "-c", "preserve_interword_spaces=1"],
        input=prepared, capture_output=True,
    )
    if recognized.returncode != 0:
        raise RuntimeError(recognized.stderr.decode(errors="replace").strip() or "Recognition failed.")
    return recognized.stdout.decode("utf-8")


def vision_model(image):
    body = {"model": MODEL, "stream": False, "think": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 4096},
            "messages": [{"role": "user", "content": PROMPT, "images": [base64.b64encode(image).decode()]}]}
    request = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)["message"]["content"]
    except OSError as error:
        raise RuntimeError(f"Accurate mode needs Ollama running with {MODEL}: {error}") from None


def main(accurate):
    capture = subprocess.run(["flameshot", "gui", "--raw", "--accept-on-select"],
                             capture_output=True)
    if not capture.stdout:
        if capture.returncode not in (0, 1):
            raise RuntimeError(capture.stderr.decode(errors="replace").strip() or "Capture failed.")
        return
    capture.check_returncode()
    text = (vision_model if accurate else tesseract)(capture.stdout).strip()
    title = f"Screenshot text ({MODEL})" if accurate else "Screenshot text (Tesseract)"
    if not text:
        subprocess.run(["notify-send", title, "No text found. Select a clearer region."], check=True)
        return
    subprocess.run(["xclip", "-selection", "clipboard", "-in"],
                   input=text.encode("utf-8"), check=True)
    subprocess.run(["notify-send", title, "Text copied to clipboard."], check=True)


if __name__ == "__main__":
    try:
        main("--accurate" in sys.argv[1:])
    except (OSError, UnicodeError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Screenshot text failed",
                        html.escape(str(error))])
