"""Private, atomic Focus Garden records. No daemon or idle polling."""

from contextlib import contextmanager
from datetime import date, datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID


TRACKS = ("study", "coding")
MILESTONES = {"first-five": "First five minutes", "first-bloom": "First bloom",
              "first-week": "First three-day week"}


def directory():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "thomas-desktop"


def defaults():
    return {"version": 1, "track": "study", "actions": {"study": "", "coding": ""},
            "sessions": [], "milestones": [],
            "reminder": {"enabled": False, "days": [1, 2, 3, 4, 5], "time": "18:00", "last_date": ""}}


def validate(data):
    def require(condition):
        if not condition:
            raise ValueError

    try:
        require(type(data["version"]) is int and data["version"] == 1 and data["track"] in TRACKS)
        require(all(isinstance(data["actions"][track], str) and len(data["actions"][track]) <= 300 for track in TRACKS))
        require(isinstance(data["sessions"], list) and isinstance(data["milestones"], list))
        require(all(item in MILESTONES for item in data["milestones"]))
        ids = set()
        for item in data["sessions"]:
            UUID(item["id"])
            require(item["id"] not in ids)
            ids.add(item["id"])
            date.fromisoformat(item["date"])
            datetime.fromisoformat(item["ended_at"])
            require(item["track"] in TRACKS)
            drift = item.get("drift", 0)
            require(type(item["seconds"]) is int and type(item["planned"]) is int and type(drift) is int
                    and 0 <= drift and 0 <= item["seconds"] and item["seconds"] + drift <= item["planned"] <= 1500)
            require(isinstance(item["win"], str) and len(item["win"]) <= 300)
        reminder = data["reminder"]
        require(type(reminder["enabled"]) is bool)
        require(isinstance(reminder["days"], list) and reminder["days"]
                and all(type(day) is int and 1 <= day <= 7 for day in reminder["days"]))
        datetime.strptime(reminder["time"], "%H:%M")
        if reminder["last_date"]:
            date.fromisoformat(reminder["last_date"])
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Focus Garden data is invalid; the original file was preserved.") from None


def load():
    path = directory() / "focus-garden.json"
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return defaults()
    except ValueError:
        raise ValueError(f"Cannot read {path}; the original file was preserved.") from None
    try:
        validate(data)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from None
    return data


def save(data):
    validate(data)
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".focus-garden-", dir=root)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(data, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, root / "focus-garden.json")
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def edit():
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(root / "focus-garden.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load()
        yield data
        save(data)


def day_totals(data):
    days = {}
    for session in data["sessions"]:
        days[session["date"]] = days.get(session["date"], 0) + session["seconds"]
    return days


def credit(state):
    """A terminal runtime snapshot is stable, so ExecStopPost can safely retry it."""
    if state.get("session_mode") != "focus" or "id" not in state:
        return None
    with edit() as data:
        if any(item["id"] == state["id"] for item in data["sessions"]):
            return None
        before = sum(item["seconds"] for item in data["sessions"])
        measured = max(0, min(state["elapsed"], state["minutes"] * 60))
        drift = max(0, min(int(state.get("drift", 0)), measured))
        seconds = measured - drift
        record = {"id": state["id"], "date": state["date"], "track": state["track"],
                  "seconds": seconds, "drift": drift, "planned": state["minutes"] * 60,
                  "ended_at": state["ended_at"], "win": ""}
        data["sessions"].append(record)
        total = before + seconds
        weeks = {}
        for day, value in day_totals(data).items():
            if value >= 300:
                parsed = date.fromisoformat(day)
                monday = parsed - timedelta(days=parsed.weekday())
                weeks[monday] = weeks.get(monday, 0) + 1
        earned = []
        for key, achieved in (("first-five", total >= 300), ("first-bloom", total >= 3000),
                              ("first-week", any(count >= 3 for count in weeks.values()))):
            if achieved and key not in data["milestones"]:
                data["milestones"].append(key)
                earned.append(MILESTONES[key])
        return {"seconds": seconds, "drift": drift, "plants": total // 3000 - before // 3000, "milestones": earned}


def summary(data, show_bloom=False, today=None):
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    days = day_totals(data)
    total = sum(days.values())
    remainder = total % 3000
    blooming = show_bloom and total > 0 and remainder == 0
    week = [{"label": (monday + timedelta(days=index)).strftime("%a"),
             "active": days.get((monday + timedelta(days=index)).isoformat(), 0) >= 300}
            for index in range(7)]
    history = [{"id": item["id"], "text": f'{item["date"]} · {item["track"].title()} · {item["seconds"] // 60}m {item["seconds"] % 60:02d}s'
                + (f' · {100 * item["seconds"] // (item["seconds"] + item["drift"])}% focused' if item.get("drift") else ""),
                "win": item["win"]} for item in reversed(data["sessions"][-10:])]
    return {"track": data["track"], "action": data["actions"][data["track"]],
            "stage": 5 if blooming else remainder // 600,
            "growth": 100 if blooming else remainder / 30,
            "growth_text": "In bloom" if blooming else f'{(600 - remainder % 600 + 59) // 60} min to next growth',
            "plants": total // 3000, "total_minutes": total // 60,
            "today_minutes": days.get(today.isoformat(), 0) // 60,
            "week": week, "week_days": sum(day["active"] for day in week),
            "study_minutes": sum(item["seconds"] for item in data["sessions"] if item["track"] == "study") // 60,
            "coding_minutes": sum(item["seconds"] for item in data["sessions"] if item["track"] == "coding") // 60,
            "milestones": [MILESTONES[key] for key in data["milestones"]], "history": history,
            "reminder": data["reminder"], "error": ""}
