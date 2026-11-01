#!/usr/bin/python3
"""Administrator installer for fixed, root-owned Login History files."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import tempfile

LIBEXEC = Path("/usr/local/libexec/i3-login-log")
DATA = Path("/var/lib/i3-login-log")
OWNER = Path("/etc/i3-login-log.json")
ACCOUNT = "i3-login-log"
FILES = {"scripts/login_service.py": "service.py", "scripts/login_store.py": "login_store.py",
         "scripts/login_log.py": "client.py", "scripts/login_failures.py": "login_failures.py",
         "setup/login_tracking_admin.py": "admin.py"}
LEGACY = {"key": ".config/i3-login-log/key", "vault.json": ".config/i3-login-log/vault.json",
          "history.db": ".local/share/i3-login-log/history.db"}


def run(*args):
    subprocess.run(args, check=True, stdin=subprocess.DEVNULL)


def safe_directory(path, mode=0o755, uid=0, gid=0):
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlinked system directory: {path}")
    if not path.exists():
        safe_directory(path.parent)
        path.mkdir(mode=mode)
        path.chmod(mode)
        os.chown(path, uid, gid)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode:
        raise RuntimeError(f"Unexpected ownership or permissions: {path}")


def install_bytes(data, destination, mode=0o644):
    safe_directory(destination.parent)
    if destination.is_symlink() or destination.exists() and not destination.is_file():
        raise RuntimeError(f"Refusing non-regular installed file: {destination}")
    if destination.exists():
        info = destination.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError(f"Installed file is not protected: {destination}")
        if destination.read_bytes() == data and stat.S_IMODE(info.st_mode) == mode:
            return False
    fd, temporary = tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def open_source(home, relative):
    """Walk without following symlinks; keep directory handles across each step."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in home.parts[1:]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = following
        parts = Path(relative).parts
        for part in parts[:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = following
        source = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        return fd, source, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def source_bytes(home, relative, uid, maximum):
    directory, fd, _ = open_source(home, relative)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077 or info.st_size > maximum:
            raise RuntimeError("Legacy source ownership, permissions or size is unexpected")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise RuntimeError("Legacy file is too large")
        return data
    finally:
        os.close(fd)
        os.close(directory)


def stage_legacy(home, uid, service):
    if (DATA / "vault").exists() or (DATA / "legacy").exists():
        return
    sources = {}
    for name, relative in LEGACY.items():
        try:
            sources[name] = source_bytes(home, relative, uid, 256 * 1024 * 1024 if name == "history.db" else 16384)
        except FileNotFoundError:
            pass
    if not sources:
        return
    if set(sources) != set(LEGACY):
        raise RuntimeError("Legacy storage is incomplete; restore its key, database and vault before migration")
    # No user-owned backup: the only staged copy belongs to the protected service.
    stage = Path(tempfile.mkdtemp(prefix=".legacy-", dir=DATA))
    try:
        manifest = {}
        for name, data in sources.items():
            path = stage / name
            path.write_bytes(data)
            path.chmod(0o600)
            os.chown(path, service.pw_uid, service.pw_gid)
            manifest[name] = hashlib.sha256(data).hexdigest()
        marker = stage / "manifest.json"
        marker.write_text(json.dumps(manifest))
        marker.chmod(0o600)
        os.chown(marker, service.pw_uid, service.pw_gid)
        os.chown(stage, service.pw_uid, service.pw_gid)
        for path in stage.iterdir():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        os.rename(stage, DATA / "legacy")
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def install(source, uid):
    account = pwd.getpwuid(uid)
    if uid < 1000 or uid == 65534:
        raise RuntimeError("Choose a regular desktop account")
    caller = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", "0")))
    if caller not in (0, uid):
        raise RuntimeError("Installer caller differs from desktop owner")
    owner = {"uid": uid, "gid": account.pw_gid, "device": "/dev/video0"}
    if OWNER.exists() or OWNER.is_symlink():
        if OWNER.is_symlink() or OWNER.stat().st_uid != 0 or OWNER.stat().st_mode & 0o022:
            raise RuntimeError("Desktop-owner configuration is not protected")
        owner = json.loads(OWNER.read_text())
        if owner.get("uid") != uid or owner.get("gid") != account.pw_gid:
            raise RuntimeError("Repeat setup cannot replace the configured desktop owner")
    if not re.fullmatch(r"/dev/video[0-9]+", owner["device"]):
        raise RuntimeError("Camera must be a fixed /dev/video device")
    packages = ("sqlcipher", "python3-nacl", "python3-gi", "gir1.2-gtk-3.0", "ffmpeg",
                "psmisc", "iproute2", "network-manager")
    installed = subprocess.run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Status}\\n", *packages],
                               capture_output=True, text=True, check=False)
    if installed.returncode or installed.stdout.splitlines() != ["installed"] * len(packages):
        run("/usr/bin/apt-get", "install", "-y", *packages)
    try:
        service = pwd.getpwnam(ACCOUNT)
        if service.pw_uid >= 1000 or service.pw_shell not in ("/usr/sbin/nologin", "/sbin/nologin"):
            raise RuntimeError("Existing service account is not a system nologin account")
    except KeyError:
        run("/usr/sbin/useradd", "--system", "--user-group", "--home-dir", str(DATA),
            "--no-create-home", "--shell", "/usr/sbin/nologin", ACCOUNT)
        service = pwd.getpwnam(ACCOUNT)
    safe_directory(LIBEXEC)
    safe_directory(DATA, mode=0o700, uid=service.pw_uid, gid=service.pw_gid)
    changed = install_bytes(json.dumps(owner).encode(), OWNER)
    for relative, name in FILES.items():
        changed |= install_bytes((source / relative).read_bytes(), LIBEXEC / name,
                                 0o755 if name == "admin.py" else 0o644)
    for name in ("service", "socket"):
        data = (source / f"setup/systemd/i3-login-log.{name}").read_text().replace("@OWNER_GID@", str(owner["gid"]))
        changed |= install_bytes(data.encode(), Path(f"/etc/systemd/system/i3-login-log.{name}"))
    changed |= install_bytes(f"[Service]\nDeviceAllow={owner['device']} rw\n".encode(),
                             Path("/etc/systemd/system/i3-login-log.service.d/camera.conf"))
    stage_legacy(Path(account.pw_dir), uid, service)
    run("/usr/bin/systemctl", "daemon-reload")
    run("/usr/bin/systemctl", "enable", "--now", "i3-login-log.socket", "i3-login-log.service")
    if changed:
        run("/usr/bin/systemctl", "restart", "i3-login-log.service")
    print("Login History service installed; initial enrollment stays local and administrator-authorized.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--uid", type=int, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Administrator authorization required")
    os.umask(0o077)
    install(args.source.resolve(), args.uid)


if __name__ == "__main__":
    main()
