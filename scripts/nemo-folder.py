#!/usr/bin/env python3
"""Stream home folders or documents into Rofi and open the selection."""

import html
from collections import deque
import os
from pathlib import Path
import subprocess
import sys


DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".rst", ".org",
    ".typ", ".tex", ".ppt", ".pptx", ".odp", ".xls", ".xlsx", ".ods", ".csv",
}


def scan_command(documents=False):
    return [sys.executable, "-u", str(Path(__file__).resolve()),
            "--scan-documents" if documents else "--scan"]


def scan_folders(documents=False):
    excluded = {"node_modules", "target", "venv", "__pycache__", "build", "dist"}
    pending = deque([Path(".")])
    if not documents:
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
                            if not documents:
                                print("~/" + str(path))
                            if not entry.is_symlink():
                                pending.append(path)
                        elif documents and path.suffix.lower() in DOCUMENT_EXTENSIONS and entry.is_file():
                            print("~/" + str(path))
                    except OSError:
                        continue
        except OSError:
            continue


def choose(documents=False, query=""):
    home = Path.home()
    scan = subprocess.Popen(scan_command(documents), cwd=home, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    options = (["-filter", query, "-format", "f\x1fs", "-kb-mode-next", "",
                "-kb-custom-1", "Control+Tab", "-mesg", "Ctrl+Tab: search PDF contents"]
               if documents else ["-format", "s", "-no-custom"])
    try:
        choice = subprocess.run(
            ["rofi", "-dmenu", "-i", "-matching", "fuzzy", "-sort",
             "-async-pre-read", "0", *options, "-theme-str",
             'entry { placeholder: "' + ("Open document…" if documents else "Open folder in Nemo…") + '"; }'],
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
    return choice


def main(documents=False):
    home = Path.home()
    query = ""
    while True:
        choice = choose(documents, query)
        typed, separator, selected = choice.stdout.partition("\x1f")
        content_query = documents and choice.returncode == 0 and separator and selected.strip() and not selected.startswith("~/")
        if documents and (choice.returncode == 10 or content_query):
            import pdf_search
            query = pdf_search.main(typed.rstrip("\n"))
            if query is None:
                return
            continue
        break
    if choice.returncode == 1:
        return
    if choice.returncode != 0:
        raise RuntimeError(choice.stderr.strip() or f"Rofi exited with status {choice.returncode}.")
    selected = choice.stdout.split("\x1f", 1)[-1].removesuffix("\n")
    if not selected:
        return
    if not selected.startswith("~/") or ".." in Path(selected[2:]).parts:
        raise RuntimeError("Invalid folder selection.")
    path = home / selected[2:]
    if not (path.is_file() if documents else path.is_dir()):
        raise RuntimeError(f"{'File' if documents else 'Folder'} no longer exists: {path}")
    subprocess.Popen(["xdg-open" if documents else "nemo", str(path)], start_new_session=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:] in (["--scan"], ["--scan-documents"]):
            scan_folders(documents=sys.argv[1] == "--scan-documents")
        else:
            main(documents=sys.argv[1:] == ["--documents"])
    except BrokenPipeError:
        pass
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Folder finder failed",
                        html.escape(str(error))])
