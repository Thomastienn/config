#!/usr/bin/env python3
"""Search official IT-Tools locally; --install downloads its pinned release."""

import argparse
import fcntl
from functools import partial
import hashlib
import html
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / "toolbox"
DATA = ROOT / ".local"
APP = DATA / "dist"
VERSION = "2024.10.22-7ca5933"
SHA256 = "eef276d675db6053bdc65cd8482a566785561c70eed5035a0e05b0e627b0989d"
DOWNLOAD = (f"https://github.com/CorentinTh/it-tools/releases/download/v{VERSION}/"
            f"it-tools-{VERSION}.zip")
ADDRESS = ("127.0.0.1", 8787)
ORIGIN = f"http://{ADDRESS[0]}:{ADDRESS[1]}"
HEALTH = "/__quick_tools_health"
IDENTITY = f"quick-tools:{VERSION}".encode()
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def tools():
    return json.loads((ROOT / "tools.json").read_text())


def install_archive(data):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("Release checksum does not match. Installation left unchanged.")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or not path.parts or path.parts[0] != "dist"
                    or ".." in path.parts or "\\" in entry.filename):
                raise RuntimeError("Release contains an unsafe archive path.")
        with tempfile.TemporaryDirectory(dir=DATA) as directory:
            archive.extractall(directory)
            unpacked = Path(directory) / "dist"
            if not (unpacked / "index.html").is_file():
                raise RuntimeError("Release does not contain the IT-Tools app.")
            shutil.copytree(unpacked, APP, dirs_exist_ok=True)


def install():
    print(f"Downloading official IT-Tools {VERSION}…", flush=True)
    with urllib.request.urlopen(DOWNLOAD, timeout=45) as response:
        data = response.read(16 * 1024 * 1024)
    install_archive(data)
    print(f"Installed {len(tools())} tools. Open with Super+U after reloading i3 config.")


class ToolHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == HEALTH:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(IDENTITY)))
            self.end_headers()
            return io.BytesIO(IDENTITY)
        if path in self.server.tool_routes:
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, *_args):
        pass


def make_server():
    server = ThreadingHTTPServer(ADDRESS, partial(ToolHandler, directory=str(APP)))
    server.tool_routes = {"/", *(tool["path"] for tool in tools())}
    return server


def server_ready():
    try:
        with LOCAL_HTTP.open(ORIGIN + HEALTH, timeout=0.3) as response:
            identity = response.read(100)
    except urllib.error.HTTPError as error:
        raise RuntimeError("Port 8787 is occupied by another app.") from error
    except OSError:
        return False
    if identity != IDENTITY:
        raise RuntimeError("Port 8787 is occupied by another app or another toolbox version.")
    return True


def ensure_server():
    if not (APP / "index.html").is_file():
        raise RuntimeError("Install first: /usr/bin/python3 " + str(Path(__file__)) + " --install")
    with (DATA / "server.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if server_ready():
            return
        with (DATA / "server.log").open("a") as log:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--serve"],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        for _ in range(50):
            if server_ready():
                return
            if process.poll() is not None:
                break
            time.sleep(0.1)
        if process.poll() is None:
            process.terminate()
        raise RuntimeError(f"Local toolbox could not start. See {DATA / 'server.log'}.")


def menu_rows(catalogue):
    rows = []
    for tool in catalogue:
        # Hidden columns remain searchable in this Rofi's dmenu mode; meta does not.
        label = f"{tool['title']} — {tool['description']}"
        terms = " ".join(tool["keywords"] + tool["aliases"])
        rows.append(label.replace("\n", " ").replace("\t", " ") + "\t" + terms)
    return "\n".join(rows)


def launch():
    catalogue = [{"title": "Browse all tools", "description": "Open the full toolbox",
                  "path": "/", "keywords": ["home", "all", "tools"], "aliases": []}, *tools()]
    choice = subprocess.run(
        # Literal tokens avoid fuzzy matches scattered across long descriptions.
        ["rofi", "-dmenu", "-sync", "-i", "-matching", "normal", "-sort", "-sorting-method", "fzf",
         "-no-custom", "-format", "i", "-display-columns", "1",
         "-display-column-separator", "\t", "-p", "Tools",
         "-theme-str", 'window { width: 800px; } mode-switcher { enabled: false; } '
         'entry { placeholder: "What do you want to do?"; }'],
        input=menu_rows(catalogue), capture_output=True, text=True,
    )
    if choice.returncode == 1:
        return
    if choice.returncode != 0:
        raise RuntimeError(choice.stderr.strip() or "Could not open tool search.")
    if not choice.stdout.strip():
        return
    selected = int(choice.stdout.strip())
    if not 0 <= selected < len(catalogue):
        raise RuntimeError("Invalid tool selection.")
    if not shutil.which("brave-browser"):
        raise RuntimeError("Brave browser is required for the toolbox window.")
    ensure_server()
    subprocess.Popen(
        ["brave-browser", f"--user-data-dir={DATA / 'browser'}", "--class=quick-tools",
         "--no-first-run", "--no-default-browser-check", "--force-dark-mode",
         "--app=" + ORIGIN + catalogue[selected]["path"]],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--install", action="store_true", help="Download and verify official IT-Tools")
    actions.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.install:
            install()
        elif args.serve:
            with make_server() as server:
                server.serve_forever()
        else:
            launch()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print(f"Quick tools: {error}", file=sys.stderr)
        if not (args.install or args.serve) and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", "critical", "Quick tools failed", html.escape(str(error))])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
