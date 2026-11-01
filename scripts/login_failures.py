"""Read native PAM password failures; never inspect password input or change PAM."""

import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import time


def failure_event(row, owner):
    if not isinstance(row, dict) or row.get("_TRANSPORT") != "syslog":
        return None
    message = row.get("MESSAGE", "")
    if not isinstance(message, str) or len(message) > 8192:
        return None
    match = re.match(r"^pam_unix\((i3lock|lightdm):auth\): authentication failure(?:;|$)", message)
    if not match:
        return None
    service = match[1]
    account = pwd.getpwuid(owner["uid"])
    if service == "i3lock":
        executables = {"/usr/bin/i3lock", "/usr/local/bin/i3lock", "/usr/local/bin/i3lock-color",
                       str(Path(account.pw_dir) / ".local/bin/i3lock")}
        if row.get("_UID") != str(owner["uid"]) or row.get("_EXE") not in executables:
            return None
    elif row.get("_UID") != "0" or row.get("_EXE") != "/usr/sbin/lightdm":
        return None
    remote = re.search(r"(?:^|\s)rhost=([^\s;]+)", message)
    if remote:
        return None
    user = re.search(r"(?:^|\s)user=([^\s;]+)", message)
    attempted = user[1] if user else "unknown"
    if service == "i3lock" and attempted not in (account.pw_name, "unknown"):
        return None
    try:
        occurred = int(row["__REALTIME_TIMESTAMP"]) / 1_000_000
        cursor = row["__CURSOR"]
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024 or not 0 <= time.time() - occurred <= 120:
            return None
    except (KeyError, ValueError, TypeError, OverflowError):
        return None
    return {"event_type": "unlock" if service == "i3lock" else "login", "result": "failure",
            "source": "pam_unix", "attempted_account": attempted[:256], "occurred_at": occurred,
            "identity": "journal:" + cursor, "pid": row.get("_PID", "")}


def monitor(application):
    """Follow new messages only; no historical backfill after Off or downtime."""
    while True:
        try:
            with subprocess.Popen([
                    "/usr/bin/journalctl", "--follow", "--lines=0", "--output=json", "--no-pager",
                    "SYSLOG_FACILITY=10", "SYSLOG_FACILITY=4"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    env={**os.environ, "SYSTEMD_COLORS": "0"}) as process:
                application.failure_monitor = True
                try:
                    while True:
                        line = process.stdout.readline(65537)
                        if not line:
                            break
                        if len(line) > 65536 or not line.endswith(b"\n"):
                            # Drop the whole oversized record, rather than parsing its tail.
                            while line and not line.endswith(b"\n"):
                                line = process.stdout.readline(65537)
                            continue
                        try:
                            event = failure_event(json.loads(line), application.owner)
                            if event is not None:
                                application.record_failure(event)
                        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                            continue
                finally:
                    application.failure_monitor = False
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            application.failure_monitor = False
        time.sleep(3)
