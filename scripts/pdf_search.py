#!/usr/bin/env python3
"""Recoll PDF content search presented through the existing Rofi document menu."""

import base64
import html
import os
from pathlib import Path
import shutil
import subprocess
import sys


def configuration():
    directory = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "thomas-pdfs"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    config = directory / "recoll.conf"
    if not config.exists():
        config.symlink_to(Path(__file__).resolve().parents[1] / "recoll/recoll.conf")
    cache = Path.home() / ".cache/thomas-pdf-search"
    cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache.chmod(0o700)
    return directory


def refresh():
    subprocess.run(["systemctl", "--user", "start", "--no-block", "thomas-pdf-index.service"], check=True)


def search(query):
    result = subprocess.run(["recollq", "-c", str(configuration()), "-C", "-n", "100",
                             "-F", "url", "-a", "--", query], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("PDF index is not ready. Press Ctrl+R to build or refresh it.")
    paths = []
    for line in result.stdout.splitlines():
        try:
            url = base64.b64decode(line.strip(), validate=True).decode()
        except (ValueError, UnicodeError):
            continue  # recollq also prints a query/result-count header.
        # Recoll's -F url field is unescaped; %, # and ? are literal filename characters.
        if not url.startswith("file:///"):
            continue
        path = Path(url.removeprefix("file://"))
        if path.suffix.lower() == ".pdf" and path.is_file():
            if path not in paths:
                paths.append(path)
    return paths


def main(query=""):
    if not shutil.which("recollq"):
        raise RuntimeError("PDF content search needs recollcmd. See scripts/PRODUCTIVITY.md for setup.")
    message = "Search words inside PDFs · Ctrl+Tab: filenames · Ctrl+R: refresh index"
    while True:
        prompt = subprocess.run(["rofi", "-dmenu", "-filter", query, "-format", "f",
                                 "-kb-mode-next", "", "-kb-custom-1", "Control+Tab",
                                 "-kb-custom-2", "Control+r", "-mesg", html.escape(message),
                                 "-theme-str", 'listview { lines: 0; } entry { placeholder: "Search PDF contents…"; }'],
                                input="", capture_output=True, text=True)
        query = prompt.stdout.strip()
        if prompt.returncode == 10:
            return query
        if prompt.returncode == 1:
            return None
        if prompt.returncode == 11:
            refresh()
            message = "Index refresh started. Try your search again shortly. · Ctrl+Tab: filenames"
            continue
        if prompt.returncode != 0:
            raise RuntimeError(prompt.stderr.strip() or "PDF search prompt failed.")
        if not query:
            continue
        try:
            paths = search(query)
        except RuntimeError as error:
            message = str(error)
            continue
        if not paths:
            message = "No matching text PDFs. Try other words, or Ctrl+R to refresh."
            continue
        labels = [str(path).replace(str(Path.home()) + "/", "~/", 1).replace("\n", " ") for path in paths]
        choice = subprocess.run(["rofi", "-dmenu", "-i", "-format", "i",
                                 "-kb-mode-next", "", "-kb-custom-1", "Control+Tab", "-mesg",
                                 html.escape(f"PDF contents: {query} · Top {len(paths)} matches · Esc: edit query")],
                                input="\n".join(labels), capture_output=True, text=True)
        if choice.returncode == 10:
            return query
        if choice.returncode == 1:
            continue
        if choice.returncode != 0:
            raise RuntimeError(choice.stderr.strip() or "PDF results menu failed.")
        index = int(choice.stdout.strip())
        if not 0 <= index < len(paths):
            message = "Choose a PDF from the results, or edit your search words."
            continue
        if not paths[index].is_file():
            message = "Selected PDF moved or was deleted. Press Ctrl+R to refresh."
            continue
        subprocess.Popen(["xdg-open", str(paths[index])], start_new_session=True)
        return None


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--index"]:
            subprocess.run(["recollindex", "-c", str(configuration())], check=True)
        else:
            main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "PDF search failed", html.escape(str(error))])
        sys.exit(1)
