#!/usr/bin/python3 -s
"""Fixed administrator enrollment bridge. Secrets travel only through pipes."""

import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import sys

from client import Client
from install import DATA, LEGACY, OWNER, open_source
from login_store import Store
from service import protect_process


def cleanup(owner):
    """Remove only unchanged old live copies, after verifying protected storage."""
    legacy = DATA / "legacy"
    if not legacy.exists():
        return False
    Store(DATA / "vault").verify()
    manifest = json.loads((legacy / "manifest.json").read_text())
    home = Path(pwd.getpwuid(owner["uid"]).pw_dir)
    checked = {}
    try:
        for name, relative in LEGACY.items():
            try:
                directory, fd, leaf = open_source(home, relative)
            except FileNotFoundError:
                continue
            checked[name] = (directory, fd, leaf)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner["uid"]
                    or info.st_size > 256 * 1024 * 1024):
                return True
            with os.fdopen(fd, "rb", closefd=False) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            current = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
            if (digest != manifest[name] or current.st_ino != info.st_ino or current.st_dev != info.st_dev
                    or os.fstat(fd).st_mtime_ns != info.st_mtime_ns):
                return True
        # Preserve every source key if any source differs; remove the database first.
        for name in ("history.db", "vault.json", "key"):
            if name in checked:
                directory, _, leaf = checked[name]
                os.unlink(leaf, dir_fd=directory)
                os.fsync(directory)
        shutil.rmtree(legacy)
        return False
    finally:
        for directory, fd, _ in checked.values():
            os.close(fd)
            os.close(directory)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise ValueError("Administrator-authorized enrollment required")
    protect_process()
    owner = json.loads(OWNER.read_text())
    caller = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", "0")))
    if caller not in (0, owner["uid"]):
        raise ValueError("Enrollment is restricted to the configured desktop owner")
    raw = sys.stdin.buffer.read(8193)
    if len(raw) > 8192:
        raise ValueError("Enrollment request too large")
    request = json.loads(raw)
    if not isinstance(request, dict) or set(request) != {"password", "old_password"}:
        raise ValueError("Invalid enrollment request")
    client = Client()
    try:
        result = client.request("enroll", **request)
    finally:
        request.clear()
        raw = b""
        client.close()
    pending = False
    try:
        pending = cleanup(owner)
    except (OSError, ValueError, RuntimeError):
        pending = True
    print(json.dumps({"ok": True, "result": result, "cleanup_pending": pending}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
