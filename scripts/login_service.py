#!/usr/bin/python3
"""Protected local login-history service; started by systemd socket activation."""

import ctypes
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import select
import secrets
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time

from nacl.exceptions import InvalidkeyError
from nacl.pwhash import argon2id

from login_store import Store, atomic_json, enroll_store
import login_failures

ROOT = Path("/var/lib/i3-login-log")
OWNER = Path("/etc/i3-login-log.json")
SOCKET = "/run/i3-login-log.sock"
MAX_REQUEST = 8192
MAX_RESPONSE = 4 * 1024 * 1024
SESSION_IDLE = 300
FRAME_TIMEOUT = 5


def protect_process():
    if ctypes.CDLL(None).prctl(4, 0, 0, 0, 0) != 0:
        raise RuntimeError("Could not disable process memory inspection")


def verifier(secret):
    return argon2id.str(secret.encode(), opslimit=argon2id.OPSLIMIT_MODERATE,
                       memlimit=argon2id.MEMLIMIT_MODERATE).decode()


def recovery_code():
    code = secrets.token_hex(32).upper()
    return "-".join(code[i:i + 8] for i in range(0, len(code), 8))


def normalized_code(value):
    return re.sub(r"[-\s]", "", value).upper()


def text(value, maximum=1024, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value.encode()) <= maximum or "\0" in value:
        raise ValueError("Invalid text field")
    return value


def valid_request(request):
    fields = {"status": (), "auth": ("password",), "set_enabled": ("enabled",),
              "list": ("date", "search", "before", "event_type", "result"), "get": ("id",), "delete": ("id",),
              "capture": (), "unlock": (), "recover": ("code", "password"), "rotate_code": (),
              "enroll": ("password", "old_password")}
    if not isinstance(request, dict) or not isinstance(request.get("op"), str):
        raise ValueError("Invalid request")
    op = request["op"]
    if op not in fields or set(request) != {"op", *fields[op]}:
        raise ValueError("Invalid operation or fields")
    for key in ("password", "old_password", "code"):
        if key in request:
            text(request[key], minimum=0 if key == "old_password" else 1)
    if op in ("recover", "enroll"):
        text(request["password"], minimum=12)
        if len(request["password"]) < 12:
            raise ValueError("Use an application password of at least 12 characters")
    if op == "set_enabled" and type(request["enabled"]) is not bool:
        raise ValueError("Tracking state must be On or Off")
    if op == "list":
        text(request["date"], maximum=10, minimum=0)
        text(request["search"], maximum=256, minimum=0)
        if request["date"]:
            datetime.strptime(request["date"], "%Y-%m-%d")
        if request["event_type"] not in ("", "login", "unlock") or request["result"] not in ("", "success", "failure"):
            raise ValueError("Invalid event or result filter")
    for key in ("id", "before"):
        if key in request and (type(request[key]) is not int or not (0 if key == "before" else 1) <= request[key] <= 2**63 - 1):
            raise ValueError("Invalid record identifier")
    return op


def session_for_pid(pid, owner_uid):
    library = ctypes.CDLL("libsystemd.so.0")
    library.sd_pid_get_session.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
    pointer = ctypes.c_void_p()
    if library.sd_pid_get_session(pid, ctypes.byref(pointer)) < 0:
        raise ValueError("Capture requires a local graphical login session")
    try:
        session = ctypes.string_at(pointer).decode()
    finally:
        libc = ctypes.CDLL(None)
        libc.free.argtypes = [ctypes.c_void_p]
        libc.free(pointer)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
        raise ValueError("Invalid login session")
    result = subprocess.run(["/usr/bin/loginctl", "show-session", session,
                             "-p", "User", "-p", "Type", "-p", "Active", "-p", "Remote",
                             "-p", "Seat", "-p", "TTY", "-p", "Timestamp"],
                            capture_output=True, text=True, timeout=4, check=True)
    details = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if (details.get("User") != str(owner_uid) or details.get("Type") != "x11"
            or details.get("Active") != "yes" or details.get("Remote") != "no"):
        raise ValueError("Capture requires the configured account's active local X11 session")
    return session, details


def metadata(owner, session, details):
    now = datetime.now().astimezone()
    data = {"trigger": "i3-login", "local_time": now.isoformat(), "timezone": now.tzname(),
            "account": pwd.getpwuid(owner["uid"]).pw_name, "uid": owner["uid"],
            "hostname": socket.gethostname(), "session": session, "login_session": details,
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "uptime_seconds": float(Path("/proc/uptime").read_text().split()[0]),
            "location": {"status": "unavailable", "reason": "No GPS source configured; no external lookup"}}
    for key, command in (("network_connections", ["/usr/bin/nmcli", "-g", "GENERAL.CONNECTION", "device", "show"]),
                         ("network_addresses", ["/usr/sbin/ip", "-j", "address", "show", "up"])):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=4, check=True)
            if key == "network_connections":
                data[key] = result.stdout.splitlines()
            else:
                data[key] = [{"interface": item["ifname"], "addresses": [a["local"] for a in item["addr_info"]]}
                             for item in json.loads(result.stdout) if item["ifname"] != "lo"]
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            data[key] = {"status": "unavailable"}
    return now, data


class CameraQuery(ctypes.Structure):
    _fields_ = [("unit", ctypes.c_uint8), ("selector", ctypes.c_uint8),
                ("query", ctypes.c_uint8), ("size", ctypes.c_uint16), ("data", ctypes.c_void_p)]


def camera_register(fd, address, value=None):
    if ctypes.sizeof(CameraQuery) != 16:
        raise RuntimeError("Camera indicator control requires the validated 64-bit UVC interface")
    packet = (ctypes.c_uint8 * 4)(address & 255, address >> 8, value or 0, 255 if value is None else 0)
    query = CameraQuery(3, 1, 1, 4, ctypes.addressof(packet))
    fcntl.ioctl(fd, 0xc0107521, query)
    if value is None:
        packet[3] = 0
        query.query = 0x81
        fcntl.ioctl(fd, 0xc0107521, query)
    return packet[2]


def validate_camera(device, indicator):
    if (not isinstance(indicator, dict)
            or set(indicator) != {"usb_id", "revision", "model", "chip_id", "direction"}
            or indicator["chip_id"] != 117 or indicator["direction"] != 7):
        raise RuntimeError("Invalid locally calibrated camera indicator profile")
    if not re.fullmatch(r"/dev/video[0-9]+", device) or str(Path(device).resolve()) != device:
        raise RuntimeError("Camera must be a fixed /dev/video device")
    usb = (Path("/sys/class/video4linux") / Path(device).name / "device").resolve()
    while usb != usb.parent and not (usb / "idVendor").exists():
        usb = usb.parent
    actual = (usb / "idVendor").read_text().strip() + ":" + (usb / "idProduct").read_text().strip()
    if (actual != indicator["usb_id"] or (usb / "bcdDevice").read_text().strip() != indicator["revision"]
            or Path("/sys/class/dmi/id/product_name").read_text().strip() != indicator["model"]):
        raise RuntimeError("Camera differs from its locally calibrated indicator profile; capture skipped")


def restore_camera(owner, root=ROOT):
    pending = root / "camera-gpio.json"
    if pending.is_symlink():
        raise RuntimeError("Refusing symlinked camera recovery state")
    if not pending.exists():
        return
    saved = json.loads(pending.read_text())
    indicator = owner.get("indicator")
    validate_camera(owner["device"], indicator)
    if saved != {"device": owner["device"], "direction": indicator["direction"]}:
        raise RuntimeError("Camera recovery state differs from its calibrated profile")
    fd = os.open(owner["device"], os.O_RDONLY | os.O_NONBLOCK)
    try:
        if (camera_register(fd, 0x101f) != indicator["chip_id"]
                or camera_register(fd, 0x1007) not in (saved["direction"], saved["direction"] & ~1)):
            raise RuntimeError("Camera state changed; recovery state retained")
        camera_register(fd, 0x1007, saved["direction"])
        if camera_register(fd, 0x1007) != saved["direction"]:
            raise RuntimeError("Camera indicator restoration failed; recovery state retained")
        pending.unlink()
    finally:
        os.close(fd)


def capture(device, indicator=None, root=ROOT):
    restore_camera({"device": device, "indicator": indicator}, root)
    busy = subprocess.run(["/usr/bin/fuser", device], capture_output=True, timeout=4)
    if busy.returncode != 1:
        raise RuntimeError("Camera is busy or ownership could not be checked")
    fd = None
    try:
        if indicator is not None:
            validate_camera(device, indicator)
            fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
            original = camera_register(fd, 0x1007)
            if (camera_register(fd, 0x101f) != indicator["chip_id"] or original != indicator["direction"]
                    or camera_register(fd, 0x1006) & 1):
                raise RuntimeError("Unexpected camera GPIO state; capture skipped")
            with (root / "camera-gpio.json").open("x") as stream:
                json.dump({"device": device, "direction": original}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            camera_register(fd, 0x1007, original & ~1)
            if camera_register(fd, 0x1007) != original & ~1:
                raise RuntimeError("Camera indicator suppression did not verify; capture skipped")
        with subprocess.Popen([
            "/usr/bin/ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "v4l2",
            "-input_format", "mjpeg", "-video_size", "640x480", "-framerate", "30", "-i", device,
            "-ss", "2", "-frames:v", "1", "-c:v", "mjpeg", "-f", "image2pipe", "pipe:1"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                photo, _ = process.communicate(timeout=10)
            except BaseException:
                process.kill()
                process.communicate()
                raise
            if (process.returncode or len(photo) > 1024 * 1024
                    or not photo.startswith(b"\xff\xd8") or not photo.endswith(b"\xff\xd9")):
                raise RuntimeError("Camera did not produce a complete JPEG")
            if fd is not None and camera_register(fd, 0x1007) != original & ~1:
                raise RuntimeError("Camera firmware changed GPIO direction during capture")
            return photo
    finally:
        if fd is not None:
            os.close(fd)
            restore_camera({"device": device, "indicator": indicator}, root)


class Service:
    def __init__(self, root, owner):
        self.root = Path(root)
        self.owner = owner
        self.lock = threading.RLock()
        self.store = Store(self.root / "vault")
        self.failure_monitor = False

    def add_event(self, now, data, identity=None):
        photo, error = None, None
        try:
            photo = capture(self.owner["device"], self.owner.get("indicator"), self.root)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            error = "Camera busy, unavailable, or capture failed"
        self.store.add(now, data, photo, error, identity)

    def record_failure(self, event):
        with self.lock:
            state = self.state()
            if state is None or not state["enabled"] or event["occurred_at"] < state.get("enabled_since", 0):
                return
            self.store.prune()
            literal = "CAST(X'" + event["identity"].encode().hex() + "' AS TEXT)"
            if self.store.database(f"SELECT session FROM captures WHERE session={literal};"):
                return
            now, data = metadata(self.owner, None, {"status": "authentication failed before session entry"})
            occurred = datetime.fromtimestamp(event["occurred_at"]).astimezone()
            data.update({key: value for key, value in event.items() if key != "identity"})
            data.update(trigger="pam-failure", local_time=occurred.isoformat(), timezone=occurred.tzname(),
                        photo_requested_at=now.isoformat())
            self.add_event(occurred, data, event["identity"])

    def state(self):
        directory = self.root / "vault"
        if not directory.exists():
            return None
        try:
            state = json.loads((directory / "state.json").read_text())
            if (state.get("version") != 1 or type(state.get("enabled")) is not bool
                    or not all(isinstance(state.get(key), str) for key in ("password", "recovery", "generation"))
                    or not all(state[key].startswith("$argon2id$") for key in ("password", "recovery"))
                    or not isinstance(state.get("attempts"), dict)
                    or not all((directory / name).is_file() for name in ("key", "private-key", "history.db"))):
                raise ValueError()
            return state
        except (OSError, ValueError, TypeError, AttributeError):
            raise RuntimeError("Protected storage is incomplete; administrator repair required. Data was preserved.") from None

    def save(self, state):
        atomic_json(self.root / "vault/state.json", state)

    def check_secret(self, state, kind, supplied):
        attempts = state["attempts"].get(kind, {})
        now = time.time()
        if now < attempts.get("next", 0):
            raise ValueError(f"Try again in {max(1, int(attempts['next'] - now) + 1)} seconds")
        try:
            argon2id.verify(state[kind].encode(), supplied.encode())
        except InvalidkeyError:
            count = attempts.get("count", 0) + 1 if now - attempts.get("last", 0) < 600 else 1
            state["attempts"][kind] = {"count": min(count, 6), "last": now,
                                        "next": now + min(30, 2 ** min(count - 1, 5))}
            self.save(state)
            raise ValueError("Incorrect password" if kind == "password" else "Incorrect recovery code") from None
        state["attempts"].pop(kind, None)
        self.save(state)

    def dispatch(self, request, uid, pid, session):
        op = valid_request(request)
        if uid != self.owner["uid"] and not (uid == 0 and op in ("status", "enroll")):
            raise ValueError("This account cannot use Login History")
        with self.lock:
            state = self.state()
            if op == "status":
                return {"setup": state is None, "enabled": state["enabled"] if state else False,
                        "migration": (self.root / "legacy").exists() if state is None else False,
                        "failure_monitor": self.failure_monitor}
            if op == "enroll":
                if uid != 0:
                    raise ValueError("Administrator-authorized setup required")
                if state is not None:
                    raise ValueError("Already enrolled; setup preserves current credentials")
                code = recovery_code()
                enroll_store(self.root, request["password"], verifier(normalized_code(code)),
                             verifier(request["password"]), request["old_password"])
                return {"code": code}
            if state is None:
                raise ValueError("Setup required: open Login History and authorize initial setup")
            if op == "auth":
                self.check_secret(state, "password", request["password"])
                session.update(generation=state["generation"], seen=time.monotonic())
                return {"authenticated": True}
            if op == "recover":
                self.check_secret(state, "recovery", normalized_code(request["code"]))
                code = recovery_code()
                state.update(password=verifier(request["password"]), recovery=verifier(normalized_code(code)),
                             generation=secrets.token_hex(16), attempts={})
                self.save(state)
                session.clear()
                return {"code": code}
            if op in ("capture", "unlock"):
                if not state["enabled"]:
                    return {"recorded": False, "reason": "Tracking is Off"}
                login, details = session_for_pid(pid, self.owner["uid"])
                boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
                identity = boot + ":" + login if op == "capture" else None
                self.store.database("CREATE TABLE IF NOT EXISTS captures(session TEXT PRIMARY KEY,created_at REAL NOT NULL);")
                literal = "CAST(X'" + identity.encode().hex() + "' AS TEXT)" if identity else "NULL"
                self.store.prune()
                if identity and self.store.database(f"SELECT session FROM captures WHERE session={literal};"):
                    return {"recorded": False, "reason": "Session already recorded"}
                now, data = metadata(self.owner, login, details)
                data.update(event_type="login" if op == "capture" else "unlock", result="success",
                            trigger="i3-login" if op == "capture" else "screen-unlock")
                self.add_event(now, data, identity)
                return {"recorded": True}
            if (session.get("generation") != state["generation"]
                    or time.monotonic() - session.get("seen", 0) >= SESSION_IDLE):
                session.clear()
                raise ValueError("Unlock required; close and reopen Login History")
            session["seen"] = time.monotonic()
            if op == "set_enabled":
                if request["enabled"] and not state["enabled"]:
                    state["enabled_since"] = time.time()
                state["enabled"] = request["enabled"]
                self.save(state)
                return {"enabled": state["enabled"]}
            if op == "rotate_code":
                code = recovery_code()
                state.update(recovery=verifier(normalized_code(code)), generation=secrets.token_hex(16))
                self.save(state)
                session.update(generation=state["generation"])
                return {"code": code}
            self.store.prune()
            if op == "list":
                return self.store.rows(request["date"], request["search"], request["before"],
                                       request["event_type"], request["result"])
            if op == "get":
                return self.store.get(request["id"])
            if op == "delete":
                self.store.delete(request["id"])
                return {"deleted": True}
        raise ValueError("Unknown operation")

    def prune(self):
        with self.lock:
            if self.state() is not None:
                self.store.prune()


def read_frame(connection, buffered):
    if not buffered and not select.select([connection], [], [], SESSION_IDLE)[0]:
        return None, b""
    deadline = time.monotonic() + FRAME_TIMEOUT
    while b"\n" not in buffered:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or len(buffered) >= MAX_REQUEST:
            raise ValueError("Incomplete or oversized request")
        connection.settimeout(remaining)
        chunk = connection.recv(MAX_REQUEST + 1 - len(buffered))
        if not chunk:
            return None, b""
        buffered += chunk
    line, remainder = buffered.split(b"\n", 1)
    if len(line) + 1 > MAX_REQUEST:
        raise ValueError("Oversized request")
    return line, remainder


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        pid, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        session = {}
        buffered = b""
        while True:
            try:
                line, buffered = read_frame(self.request, buffered)
                if line is None:
                    return
            except (OSError, ValueError):
                return
            try:
                result = self.server.application.dispatch(json.loads(line), uid, pid, session)
                response = {"ok": True, "result": result}
            except (ValueError, RuntimeError) as error:
                response = {"ok": False, "error": str(error)}
            except (OSError, subprocess.SubprocessError, KeyError, TypeError):
                response = {"ok": False, "error": "Login History operation failed; stored data was preserved"}
            encoded = json.dumps(response, ensure_ascii=False).encode() + b"\n"
            if len(encoded) > MAX_RESPONSE:
                encoded = b'{"ok":false,"error":"Response too large"}\n'
            try:
                self.request.settimeout(5)
                self.request.sendall(encoded)
            except OSError:
                return


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, listener, application):
        super().__init__(SOCKET, Handler, bind_and_activate=False)
        self.socket.close()
        self.socket = listener
        self.application = application
        self.slots = threading.BoundedSemaphore(8)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        super().process_request(request, address)

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def main():
    os.umask(0o077)
    protect_process()
    owner = json.loads(OWNER.read_text())
    restore_camera(owner)
    if sys.argv[1:] == ["restore-camera"]:
        return
    application = Service(ROOT, owner)
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise RuntimeError("Start Login History using its systemd socket")
    listener = socket.socket(fileno=3)
    listener.set_inheritable(False)

    def cleanup():
        while True:
            try:
                application.prune()
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                pass
            time.sleep(300)

    threading.Thread(target=cleanup, daemon=True).start()
    threading.Thread(target=login_failures.monitor, args=(application,), daemon=True).start()
    with Server(listener, application) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
