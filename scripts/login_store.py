"""Service-owned SQLCipher storage. No desktop process receives encryption keys."""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox
from nacl.pwhash import argon2id
from nacl.secret import SecretBox

RETENTION = 7 * 24 * 60 * 60
SQLCIPHER = "/usr/bin/sqlcipher"


def atomic_json(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(data, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def database(self, statement):
        key = (self.path / "key").read_text().strip()
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise RuntimeError("Invalid database key")
        commands = ('.output /dev/null\n'
                    f'PRAGMA key = "x\'{key}\'";\n'
                    'PRAGMA cipher_memory_security = ON;\n'
                    'PRAGMA secure_delete = ON;\nPRAGMA temp_store = MEMORY;\n'
                    '.output stdout\n.mode json\n.timeout 5000\n' + statement + "\n")
        result = subprocess.run([SQLCIPHER, "-batch", "-bail", str(self.path / "history.db")],
                                input=commands, text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError("Encrypted database operation failed; stored data was preserved")
        return json.loads(result.stdout) if result.stdout.strip() else []

    def private_key(self):
        return PrivateKey(bytes.fromhex((self.path / "private-key").read_text().strip()))

    def verify(self):
        key = self.private_key()
        if self.database("PRAGMA quick_check;") != [{"quick_check": "ok"}]:
            raise RuntimeError("Encrypted database integrity check failed")
        if self.database("PRAGMA cipher_integrity_check;"):
            raise RuntimeError("Encrypted database authentication failed")
        for row in self.database("SELECT id,created_at,hex(sealed) AS sealed FROM events;"):
            self.decode(row, key)

    def decode(self, row, key=None):
        try:
            payload = json.loads(SealedBox(key or self.private_key()).decrypt(bytes.fromhex(row["sealed"])))
            if (not isinstance(payload, dict)
                    or any(not isinstance(payload.get(field), str) for field in
                           ("local_time", "name", "metadata", "photo"))
                    or payload.get("created_at") != row["created_at"]
                    or payload.get("photo_error") is not None and not isinstance(payload["photo_error"], str)
                    or not isinstance(json.loads(payload["metadata"]).get("account"), str)):
                raise ValueError()
            bytes.fromhex(payload["photo"])
            return {**payload, "id": row["id"]}
        except (CryptoError, ValueError, TypeError, KeyError, AttributeError):
            raise RuntimeError("An encrypted record failed authentication or validation") from None

    def prune(self):
        cutoff = time.time() - RETENTION
        self.database(f"DELETE FROM events WHERE created_at <= {cutoff!r};"
                      f"DELETE FROM captures WHERE created_at <= {cutoff!r};")

    def add(self, now, details, photo=None, error=None, session=None):
        payload = {"created_at": now.timestamp(), "local_time": now.isoformat(),
                   "name": now.strftime("%Y-%m-%d/%H-%M-%S.%f%z"),
                   "metadata": json.dumps(details, ensure_ascii=False),
                   "photo": photo.hex() if photo else "", "photo_error": error}
        sealed = SealedBox(self.private_key().public_key).encrypt(json.dumps(payload, ensure_ascii=False).encode())
        prefix = "BEGIN;"
        if session is not None:
            literal = "CAST(X'" + session.encode().hex() + "' AS TEXT)"
            prefix += f"INSERT INTO captures(session,created_at) VALUES ({literal},{now.timestamp()!r});"
        self.database(prefix + "INSERT INTO events(created_at,local_time,name,metadata,sealed) VALUES ("
                      f"{now.timestamp()!r},'','','{{}}',X'{sealed.hex()}');COMMIT;")

    def rows(self, date="", search="", before=0, event_type="", result=""):
        if date:
            datetime.strptime(date, "%Y-%m-%d")
        bound = f" AND id < {before}" if before else ""
        rows = self.database("SELECT id,created_at,hex(sealed) AS sealed FROM events WHERE "
                             f"created_at > {time.time() - RETENTION!r}{bound} ORDER BY id DESC LIMIT 50;")
        results = []
        for row in rows:
            payload = self.decode(row)
            details = json.loads(payload["metadata"])
            kind = details.get("event_type", "login")
            outcome = details.get("result", "success")
            if ((not date or payload["local_time"][:10] == date)
                    and search.casefold() in payload["metadata"].casefold()
                    and (not event_type or kind == event_type) and (not result or outcome == result)):
                results.append({k: v for k, v in payload.items() if k != "photo"}
                               | {"has_photo": bool(payload["photo"]), "event_type": kind, "result": outcome})
        return {"rows": results, "next": rows[-1]["id"] if len(rows) == 50 else 0}

    def get(self, record_id):
        rows = self.database("SELECT id,created_at,hex(sealed) AS sealed FROM events WHERE "
                             f"id={record_id} AND created_at > {time.time() - RETENTION!r};")
        if not rows:
            raise ValueError("Record expired or was deleted; refresh history")
        return self.decode(rows[0])

    def delete(self, record_id):
        self.database(f"DELETE FROM events WHERE id={record_id};")


def enroll_store(root, password, recovery_hash, password_hash, old_password):
    """Commit a complete vault with one directory rename; never overwrite a vault."""
    destination = root / "vault"
    if destination.exists():
        raise RuntimeError("Storage already exists; enrollment cannot replace it")
    stage = Path(tempfile.mkdtemp(prefix=".enroll-", dir=root))
    try:
        legacy = root / "legacy"
        store = Store(stage)
        if legacy.exists():
            required = ("key", "history.db", "vault.json")
            if not all((legacy / name).is_file() for name in required):
                raise RuntimeError("Legacy storage is incomplete; source files were preserved")
            descriptor = json.loads((legacy / "vault.json").read_text())
            try:
                derived = argon2id.kdf(SecretBox.KEY_SIZE, old_password.encode(),
                                      bytes.fromhex(descriptor["salt"]),
                                      opslimit=argon2id.OPSLIMIT_MODERATE,
                                      memlimit=argon2id.MEMLIMIT_MODERATE)
                private = PrivateKey(SecretBox(derived).decrypt(bytes.fromhex(descriptor["private_key"])))
            except (CryptoError, ValueError, KeyError):
                raise ValueError("Incorrect previous vault password or damaged legacy vault") from None
            if bytes(private.public_key).hex() != descriptor["public_key"]:
                raise RuntimeError("Legacy vault keys do not match")
            for name in ("key", "history.db"):
                shutil.copyfile(legacy / name, stage / name)
            (stage / "private-key").write_text(bytes(private).hex())
            for row in store.database("SELECT id,created_at,local_time,name,metadata,hex(photo) AS photo,photo_error "
                                      "FROM events WHERE sealed IS NULL;"):
                payload = {key: value for key, value in row.items() if key != "id"}
                payload["photo"] = payload["photo"] or ""
                sealed = SealedBox(private.public_key).encrypt(json.dumps(payload).encode())
                store.database(f"UPDATE events SET sealed=X'{sealed.hex()}',local_time='',name='',metadata='{{}}',"
                               f"photo=NULL,photo_error=NULL WHERE id={int(row['id'])};")
        else:
            (stage / "key").write_text(os.urandom(32).hex())
            (stage / "private-key").write_text(bytes(PrivateKey.generate()).hex())
            store.database("CREATE TABLE events(id INTEGER PRIMARY KEY,created_at REAL NOT NULL,"
                           "local_time TEXT NOT NULL,name TEXT NOT NULL,metadata TEXT NOT NULL,"
                           "photo BLOB,photo_error TEXT,sealed BLOB);"
                           "CREATE INDEX events_created_at ON events(created_at);")
        store.database("CREATE TABLE IF NOT EXISTS captures(session TEXT PRIMARY KEY,created_at REAL NOT NULL);")
        store.verify()
        state = {"version": 1, "password": password_hash, "recovery": recovery_hash,
                 "enabled": False, "generation": os.urandom(16).hex(),
                 "attempts": {}, "sessions": []}
        atomic_json(stage / "state.json", state)
        for path in stage.iterdir():
            path.chmod(0o600)
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        sync_directory(stage)
        os.rename(stage, destination)
        sync_directory(root)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
