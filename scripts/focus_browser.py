#!/usr/bin/python3
"""Private native-messaging bridge for the paired Brave profile. No network listener."""

import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import threading
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
HOST = "org.thomas.focus"
LIMIT = 1024 * 1024


def directory():
    path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "thomas-desktop"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def extension_id():
    key = json.loads((ROOT / "brave/focus-guard/manifest.json").read_text())["key"]
    return "".join(chr(97 + int(char, 16)) for char in hashlib.sha256(base64.b64decode(key)).hexdigest()[:32])


def connect():
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(5)
    try:
        client.connect(str(directory() / "focus-browser.sock"))
    except OSError:
        client.close()
        raise RuntimeError("Lock In needs its Brave extension. Run setup, load brave/focus-guard, then click the extension.") from None
    return client


def receive(stream):
    line = stream.readline(LIMIT + 1)
    if not line or len(line) > LIMIT or not line.endswith(b"\n"):
        raise ValueError("Invalid browser bridge message")
    data = json.loads(line)
    if not isinstance(data, dict):
        raise ValueError("Invalid browser bridge object")
    return data


def request(op, **fields):
    with connect() as client:
        client.sendall(json.dumps({"op": op, **fields}).encode() + b"\n")
        with client.makefile("rb") as stream:
            reply = receive(stream)
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "Browser enforcement is unavailable"))
        return reply


def subscribe():
    client = connect()
    client.sendall(b'{"op":"subscribe"}\n')
    client.settimeout(None)
    return client


def host():
    if sys.argv[1:] != [f"chrome-extension://{extension_id()}/"]:
        raise ValueError("Unexpected extension origin")
    path = directory() / "focus-browser.sock"
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode) or path.stat().st_uid != os.getuid():
            raise RuntimeError("Browser bridge path is not an owned socket")
        with socket.socket(socket.AF_UNIX) as probe:
            try:
                probe.connect(str(path))
            except (ConnectionRefusedError, FileNotFoundError):
                path.unlink(missing_ok=True)
            else:
                raise RuntimeError("Another Brave profile is already paired")
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    os.chmod(path, 0o600)
    server.listen(8)
    output_lock = threading.Lock()
    state_lock = threading.Lock()
    subscribers, pending = set(), {}

    def send_native(data):
        body = json.dumps(data).encode()
        if len(body) > LIMIT:
            raise ValueError("Browser message is too large")
        with output_lock:
            sys.stdout.buffer.write(struct.pack("=I", len(body)) + body)
            sys.stdout.buffer.flush()

    def broadcast(data):
        body = json.dumps(data).encode() + b"\n"
        with state_lock:
            listeners = list(subscribers)
        for listener in listeners:
            try:
                listener.sendall(body)
            except OSError:
                with state_lock:
                    subscribers.discard(listener)

    def serve(client):
        token = None
        try:
            client.settimeout(6)
            with client.makefile("rb") as stream:
                data = receive(stream)
            op = data.get("op")
            if op == "subscribe":
                client.settimeout(None)
                with state_lock:
                    subscribers.add(client)
                while client.recv(1):
                    pass
                return
            if op == "control":
                if data.get("action") not in ("resume", "approve_window", "end") or not isinstance(data.get("session"), str):
                    raise ValueError("Invalid focus control")
                broadcast({"event": "control", "session": data["session"], "action": data["action"]})
                reply = {"ok": True}
            else:
                if op not in ("snapshot", "status", "start", "approve", "stop", "ui"):
                    raise ValueError("Unknown browser operation")
                token = uuid4().hex
                arrived, reply = threading.Event(), {}
                with state_lock:
                    pending[token] = (arrived, reply)
                send_native({**data, "id": token})
                if not arrived.wait(5):
                    raise RuntimeError("Browser enforcement did not acknowledge the request")
            client.sendall(json.dumps(reply).encode() + b"\n")
        except (OSError, ValueError, RuntimeError) as error:
            try:
                client.sendall(json.dumps({"ok": False, "error": str(error)}).encode() + b"\n")
            except OSError:
                pass
        finally:
            with state_lock:
                subscribers.discard(client)
                pending.pop(token, None)
            client.close()

    def accept():
        while True:
            try:
                client, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=serve, args=(client,), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    try:
        while True:
            header = sys.stdin.buffer.read(4)
            if not header:
                break
            if len(header) != 4:
                raise ValueError("Truncated native message")
            length = struct.unpack("=I", header)[0]
            if not 0 < length <= LIMIT:
                raise ValueError("Invalid native message size")
            body = sys.stdin.buffer.read(length)
            if len(body) != length:
                raise ValueError("Truncated native message")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("Invalid native message")
            if "event" in data:
                broadcast(data)
            else:
                with state_lock:
                    item = pending.get(data.get("id"))
                if item:
                    arrived, reply = item
                    reply.update(data)
                    arrived.set()
    finally:
        server.close()
        path.unlink(missing_ok=True)
        with state_lock:
            listeners = list(subscribers)
        for listener in listeners:
            try:
                listener.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            listener.close()


if __name__ == "__main__":
    try:
        host()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Focus browser: {error}", file=sys.stderr)
        sys.exit(1)
