"""Install and inspect the protected Login History service from normal setup."""

import json
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
LIBEXEC = Path("/usr/local/libexec/i3-login-log")
INSTALLER = LIBEXEC / "install.py"
CODE = {"scripts/login_service.py": "service.py", "scripts/login_store.py": "login_store.py",
        "scripts/login_log.py": "client.py", "scripts/login_failures.py": "login_failures.py",
        "setup/login_tracking_admin.py": "admin.py",
        "setup/login_tracking_install.py": "install.py"}
OLD_UNITS = ("i3-login-log.service", "i3-login-log-prune.service", "i3-login-log-prune.timer")


def matches(source, target, mode):
    try:
        info = target.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and stat.S_IMODE(info.st_mode) == mode and target.read_bytes() == source.read_bytes())
    except FileNotFoundError:
        return False


def retire_user_units(home, run):
    directory = home / ".config/systemd/user"
    owned = []
    for name in OLD_UNITS:
        path = directory / name
        if path.is_symlink() and Path(os.readlink(path)) == REPO / "systemd/user" / name:
            owned.append(path)
    if not owned:
        return
    for name in ("i3-login-log-prune.timer", "i3-login-log.service"):
        active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", name],
                                capture_output=True, timeout=5)
        if active.returncode == 0:
            run(["systemctl", "--user", "stop", name])
    for name in OLD_UNITS:
        enabled = directory / "timers.target.wants" / name
        if enabled.is_symlink() and enabled.resolve(strict=False) == (directory / name).resolve(strict=False):
            enabled.unlink()
    for path in owned:
        path.unlink()
    run(["systemctl", "--user", "daemon-reload"])


def install(run):
    retire_user_units(Path.home(), run)
    if not matches(ROOT / "login_tracking_install.py", INSTALLER, 0o755):
        if INSTALLER.is_symlink():
            raise RuntimeError("Refusing symlinked privileged Login History installer")
        run(["sudo", "install", "-D", "-o", "root", "-g", "root", "-m", "755",
             ROOT / "login_tracking_install.py", INSTALLER])
    run(["sudo", INSTALLER, "--source", REPO, "--uid", os.getuid()])


def check():
    gaps = []
    for relative, name in CODE.items():
        mode = 0o755 if name in ("install.py", "admin.py") else 0o644
        if not matches(REPO / relative, LIBEXEC / name, mode):
            gaps.append(f"login history: protected installed copy {name}")
    try:
        for unit in ("i3-login-log.socket", "i3-login-log.service"):
            result = subprocess.run(["systemctl", "is-enabled", unit], capture_output=True,
                                    text=True, timeout=3)
            if result.returncode or result.stdout.strip() != "enabled":
                gaps.append(f"login history: {unit} not enabled")
        import sys
        sys.path.insert(0, str(REPO / "scripts"))
        import login_log
        if login_log.status()["setup"]:
            gaps.append("login history: open Login History for administrator-authorized enrollment")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        gaps.append("login history: protected service unavailable")
    return gaps
