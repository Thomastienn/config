#!/usr/bin/env python3
"""Install this checkout's user units without replacing unrelated configuration."""

import os
from pathlib import Path
import shutil
import subprocess

import pdf_search


repo = Path(__file__).resolve().parents[1]
units = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user"
units.mkdir(parents=True, exist_ok=True)
for source in (repo / "systemd/user").glob("thomas-*"):
    target = units / source.name
    if target.is_symlink() and target.resolve() == source:
        continue
    if target.exists() or target.is_symlink():
        raise SystemExit(f"Existing configuration left untouched: {target}")
    target.symlink_to(source)
pdf_search.configuration()
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
environment = [name for name in ("DISPLAY", "XAUTHORITY") if os.environ.get(name)]
if environment:
    subprocess.run(["systemctl", "--user", "import-environment", *environment], check=True)
if shutil.which("recollq") and shutil.which("recollindex"):
    subprocess.run(["systemctl", "--user", "enable", "--now", "thomas-pdf-index.timer"], check=True)
    subprocess.run(["systemctl", "--user", "start", "--no-block", "thomas-pdf-index.service"], check=True)
    print("User services installed; PDF indexing started.")
else:
    print("Focus/AFK services installed. PDF search still needs recollcmd; rerun this installer after installing it.")
print("Restart i3 once for the AFK socket.")
print("Reload Eww/Polybar and Dunst when ready. New shell tabs load command alerts automatically.")
