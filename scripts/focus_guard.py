#!/usr/bin/env python3
"""Lock-in guard for one focus session: judge the focused window, nudge, hide, and measure drift.

Runs only while thomas-focus.service is in focus mode. Event-driven: it sleeps until an i3
window event, model loading, or its next deadline. Rules, user overrides, and the local
Decima model decide window actions. 9router only writes session themes, reflections, and
notification/reward wording; its output never changes decisions or earned progress.
"""

import ctypes
import gc
import json
import os
from pathlib import Path
import random
import re
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

STATE = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "thomas-desktop"
RULES_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "thomas-desktop/focus-rules.json"
MODEL = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "thomas-desktop/decima-small/onnx/int8"
MEMORY = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "thomas-desktop/focus-verdicts.json"
VOICE = MEMORY.with_name("focus-voice.json")
ROUTER = "http://127.0.0.1:20128/v1/chat/completions"
CONTROLS = Path(__file__).with_name("desktop-controls.py")

DWELL = 8        # seconds on a window before judging it; quick alt-tabs are ignored
HOME_DWELL = 90  # the bare YouTube feed gets time to search for material first
GRACE = 20       # seconds after a nudge before a distraction is hidden
AWAY = 300_000   # idle milliseconds before an unproductive window counts as away
UNLOAD = 300     # seconds without a new title before Decima leaves memory
REMEMBER = 5000  # verdicts kept across sessions
ACT = 0.7
LABELS = ("on_task", "distraction", "neutral")
BROWSERS = ("brave", "firefox", "chrome", "chromium")
RULES = {
    "on_task_apps": ["kitty", "cursor", "code", "zathura", "evince", "okular", "xournalpp", "obsidian",
                     "libreoffice", "soffice", "jetbrains"],
    "block_apps": ["discord", "vesktop", "sober", "steam", "roblox"],
    "neutral_apps": ["eww", "rofi", "nemo", "copyq", "pavucontrol", "blueman", "zoom"],
    "on_task_titles": ["chatgpt", "claude", "gemini", "perplexity"],
    "neutral_titles": ["gmail", "outlook", "new tab", "calendar"],
}
LINES = {  # used until, or unless, 9router writes this session's lines
    "theme": ["One small promise", "A little further", "Quiet momentum", "Room to grow"],
    "thought": ["You do not need to finish everything to move something forward.",
                "Make the next step small enough that you can begin it now.",
                "Returning to the task is part of doing the task.",
                "Some progress is too quiet to notice while it is happening."],
    "start": ["Lock-in on. Distractions are napping.", "Garden gates closed. Just you and the task."],
    "nudge": ["Drifting?", "That doesn't look like the task…", "Your plant is watching.", "Quick detour?"],
    "hide": ["Tucked away until the session ends.", "Out of sight. Back to the task."],
    "away": ["Still there?", "The garden got quiet…"],
    "done": ["Nice work.", "Session complete. The garden noticed."],
    "bloom": ["A new plant bloomed!", "Another bloom, grown one small step at a time."],
    "milestone": ["A new milestone took root.", "A small effort became a lasting marker."],
}


def i3(command):
    subprocess.run(["i3-msg", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)


def windows():
    """(con_id, class, title, workspace, floating, focused) for every client window."""
    def walk(node, workspace, floating):
        if node.get("type") == "workspace":
            workspace = node["name"]
        if node.get("window"):
            yield (node["id"], (node.get("window_properties") or {}).get("class", ""), node.get("name") or "",
                   workspace, floating, node.get("focused", False))
        for child in node.get("nodes", []):
            yield from walk(child, workspace, floating)
        for child in node.get("floating_nodes", []):
            yield from walk(child, workspace, True)
    tree = json.loads(subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True, text=True, timeout=5).stdout)
    return list(walk(tree, "", False))


def clean(title):
    title = re.sub(r"^\(\d+\)\s*", "", title)
    return re.sub(r"\s+[-—]\s+(Brave|Mozilla Firefox|Google Chrome|Chromium)$", "", title, flags=re.I).strip()


def rules():
    merged = {key: list(value) for key, value in RULES.items()}
    try:
        for key, value in json.loads(RULES_FILE.read_text()).items():
            if key in merged and isinstance(value, list):
                merged[key] += [str(item).lower() for item in value]
    except (OSError, ValueError, AttributeError):
        pass
    return merged


def rule(app, title, table):
    app, title = app.lower(), title.lower()
    if any(item in app for item in table["block_apps"]) or clean(title) == "youtube":
        return "distraction"
    if any(item in app for item in table["on_task_apps"]) or any(item in title for item in table["on_task_titles"]):
        return "on_task"
    if any(item in app for item in table["neutral_apps"]) or any(item in title for item in table["neutral_titles"]):
        return "neutral"
    return None


def router(prompt, temperature=0.0):
    body = {"model": "free", "stream": False, "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request(ROUTER, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode()
    # 9router may stream even when asked not to; join any SSE deltas.
    if text.lstrip().startswith("data:"):
        return "".join((json.loads(line[5:])["choices"] or [{}])[0].get("delta", {}).get("content") or ""
                       for line in text.splitlines() if line.startswith("data:") and "[DONE]" not in line)
    return json.loads(text)["choices"][0]["message"]["content"]


class Judge:
    """Rules and user overrides first, then local content classification; uncertainty is neutral."""

    def __init__(self, task, track, wake=lambda: None):
        self.task, self.track, self.table, self.wake = task, track, rules(), wake
        self.model = None
        self.loading = self.failed = False
        self.used = 0.0
        self.status = "Lock-in on"
        self.answers = {}   # key -> label, or None while undecided
        self.lines = {kind: list(items) for kind, items in LINES.items()}
        try:
            self.memory = {key: value for key, value in json.loads(MEMORY.read_text()).items()
                           if key.startswith("local-v1\t") and value in LABELS}
        except (OSError, ValueError, AttributeError, TypeError):
            self.memory = {}
        try:
            recent = json.loads(VOICE.read_text())
            self.recent = ([line for line in recent if isinstance(line, str) and len(line) <= 160][-60:]
                           if isinstance(recent, list) else [])
        except (OSError, ValueError):
            self.recent = []
        self.voice = {kind: self.line(kind) for kind in ("theme", "thought")}
        threading.Thread(target=self.write_lines, daemon=True).start()

    def slot(self, key, scope=None):
        # Old entries mix LLM verdicts and clicks, so they cannot serve as local decisions.
        return "\t".join(("local-v1", scope or self.task, *key))

    def remember(self, key, verdict, scope=None):
        self.memory.pop(self.slot(key, scope), None)  # re-insert so pruning drops the stalest
        self.memory[self.slot(key, scope)] = verdict

    def save_memory(self):
        for path, data in ((MEMORY, dict(list(self.memory.items())[-REMEMBER:])), (VOICE, self.recent[-60:])):
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix=".focus-", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w") as output:
                    json.dump(data, output, ensure_ascii=False)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def unload(self, now):
        if self.model and now - self.used >= UNLOAD:
            self.model = None
            gc.collect()
            try:  # glibc keeps freed model memory unless asked to return it (~480 MB back).
                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except (OSError, AttributeError):
                pass

    def load(self):
        try:
            from decima import Decima, Question
            # shortcut: genre does not establish task relevance; use a stronger local model if needed.
            self.video = Question("What kind of video is this?", [
                "entertainment video (gaming, reactions, music, variety show, vlog, comedy, sports)",
                "educational or technical video (lecture, tutorial, explainer, programming, math, science)"])
            self.page = Question("What kind of content is this?", [
                "entertainment: gaming, reactions, music, variety or game shows, vlogs, comedy, sports, streams, "
                "social media feeds, memes, shopping",
                "educational or work: lecture, tutorial, explainer, documentation, programming, math, science, "
                "coursework, search results",
                "utility: email, calendar, new tab, settings"])
            if not MODEL.is_dir():
                raise FileNotFoundError("Local Decima model missing; run ./setup.sh apply")
            self.model = Decima.from_pretrained(MODEL)
        except Exception as error:  # Missing venv/model must not stop the session.
            self.failed = True
            self.status = "Lock-in on · rules only (no local model)"
            print(f"Decima unavailable: {error}", file=sys.stderr)
        self.loading = False
        self.wake()

    def line(self, kind):
        choices = [line for line in self.lines[kind] if line not in self.recent]
        previous = next((line for line in reversed(self.recent) if line in self.lines[kind]), None)
        alternatives = [line for line in self.lines[kind] if line != previous]
        line = random.choice(choices or alternatives or self.lines[kind])
        self.recent = (self.recent + [line])[-60:]
        return line

    def write_lines(self):
        tone = random.choice(("quietly philosophical", "warm and grounded", "witty and deadpan", "playful garden adventure"))
        prompt = ("Write original lines for a student's focus app themed around a garden that grows while they focus. "
                  f"Track: {self.track}. Task (context only): {json.dumps(self.task)}. Tone this session: {tone}. "
                  "No guilt, pressure, invented achievements, statistics, or attributed quotations. No emoji or markup. "
                  "Themes at most 48 characters, reflections at most 160, other lines at most 90. "
                  f"Avoid repeating these recently used lines: {json.dumps(self.recent[-20:])}. "
                  'Return only JSON: {"theme": [1 short session theme], "thought": [2 reflective or motivating lines], '
                  '"start": [3 lines opening a session], "nudge": [6 lines asking if they '
                  'drifted off-task], "hide": [4 lines saying the distraction was tucked away], "away": [3 lines '
                  'asking if they are still there], "done": [3 lines acknowledging effort even if stopped early], '
                  '"bloom": [3 lines celebrating an earned plant], "milestone": [3 lines celebrating an earned milestone]}.')
        try:
            text = router(prompt, temperature=1.0)
            written = json.loads(text[text.index("{"): text.rindex("}") + 1])
            for kind in LINES:
                items = written.get(kind, [])
                if not isinstance(items, list):
                    continue
                limit = 160 if kind == "thought" else 48 if kind == "theme" else 90
                fresh = list(dict.fromkeys(line.strip() for line in items if isinstance(line, str)
                                          and line.strip().isprintable() and 0 < len(line.strip()) <= limit
                                          and line.strip() not in self.recent))[:6]
                if fresh:
                    self.lines[kind] = fresh
            self.voice = {kind: self.line(kind) for kind in ("theme", "thought")}
            self.wake()
        except (OSError, ValueError, KeyError, IndexError, AttributeError, TypeError):
            pass

    def __call__(self, app, title):
        """A label, or None while undecided."""
        key = (app, clean(title))
        if key in self.answers:
            return self.answers[key]
        verdict = self.memory.get(self.slot(key)) or rule(app, title, self.table) or self.memory.get(self.slot(key, "*"))
        if verdict:
            self.answers[key] = verdict
            return verdict
        self.used = time.monotonic()
        model = self.model
        if not model and not self.failed:
            if not self.loading:
                self.loading = True
                threading.Thread(target=self.load, daemon=True).start()
            return None
        verdict = "neutral"
        if model:
            try:
                if key[1].endswith(" - YouTube"):
                    probs = model.decide(f'YouTube video title: "{key[1][:-10]}"', self.video).probs
                else:
                    browser = any(name in app.lower() for name in BROWSERS)
                    probs = model.decide(f'Window title: "{key[1]}"' if browser else f'{app} window: "{key[1]}"',
                                         self.page).probs
                if probs[0] >= ACT:
                    verdict = "distraction"
                elif probs[1] >= ACT:
                    verdict = "on_task"
                self.remember(key, verdict, "*")
            except Exception as error:
                self.model, self.failed = None, True
                self.status = "Lock-in on · rules only (local model failed)"
                print(f"Decima unavailable: {error}", file=sys.stderr)
        self.answers[key] = verdict
        return verdict


class Guard:
    def __init__(self):
        focus = json.loads((STATE / "focus.json").read_text())
        self.wake_read, self.wake_write = os.pipe()
        os.set_blocking(self.wake_write, False)
        self.judge = Judge(focus.get("task") or "One small step", focus.get("track", "study"), self.poke)
        self.session = {"id": focus["id"], "drift": 0, "nudges": 0, "hidden": [], "status": self.judge.status,
                        "voice": self.judge.voice}
        self.allowed = set()
        self.window_drift = {}
        self.current = None      # (con_id, app, title)
        self.since = self.accounted = time.monotonic()
        self.verdict = None
        self.nudged_at = self.nudged_key = None
        self.last_on_task = None
        self.idle = self.idle_check = 0
        self.running = True

    def poke(self):
        """Wake the main loop; safe from threads and signal handlers."""
        try:
            os.write(self.wake_write, b".")
        except BlockingIOError:
            pass

    def save(self, refresh=False):
        self.session["drift"] = int(self.session["drift"])
        temporary = STATE / ".focus-guard.json"
        temporary.write_text(json.dumps(self.session))
        os.replace(temporary, STATE / "focus-guard.json")
        if refresh:
            subprocess.Popen(["/usr/bin/python3", str(CONTROLS), "focus-refresh"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def notify(self, title, body, allow=None):
        args = ["notify-send", "-a", "Focus", "-t", "15000", title, body]
        if allow is None:
            subprocess.run(args, timeout=5)
            return

        def wait():
            # Left click runs the default action; dismissing prints nothing.
            result = subprocess.run(args[:-2] + ["-A", "default=It's for my task", title, body],
                                    capture_output=True, text=True)
            if result.stdout.strip() == "default":
                self.allowed.add(allow)
                self.judge.remember(allow, "on_task")
                self.poke()
        threading.Thread(target=wait, daemon=True).start()

    def hide(self, con_id, workspace, floating):
        i3(f"[con_id={con_id}] move scratchpad")
        self.session["hidden"].append({"con": con_id, "workspace": workspace, "floating": floating})

    def preblock(self):
        names = []
        for con_id, app, _title, workspace, floating, _focused in windows():
            if workspace != "__i3_scratch" and rule(app, "", self.judge.table) == "distraction":
                self.hide(con_id, workspace, floating)
                names.append(app)
        if names:
            self.notify(self.judge.line("start"), "Hid " + ", ".join(sorted(set(names))) + " until this session ends.")

    def refocus(self):
        current = next(((con_id, app, title) for con_id, app, title, _workspace, _floating, focused in windows()
                        if focused), None)
        if current != self.current:
            self.current, self.verdict = current, None
            self.since = self.accounted = time.monotonic()
            self.idle = self.idle_check = 0

    def dwell(self):
        return HOME_DWELL if self.current and clean(self.current[2]).lower() == "youtube" else DWELL

    def deadline(self, now):
        """When the next timer-driven change is due, or None to sleep until an event."""
        due = [self.judge.used + UNLOAD] if self.judge.model else []
        if self.current and self.verdict is None:
            due.append(self.since + self.dwell())
        if self.verdict == "distraction" and self.nudged_at is not None:
            due.append(max(self.nudged_at, self.since) + GRACE)
        if self.verdict == "neutral":
            due.append(self.idle_check)
        # Past-due work was done by the last tick; anything still pending waits for a poke.
        return min((t for t in due if t > now), default=None)

    def away(self, now):
        if now >= self.idle_check:
            try:
                self.idle = int(subprocess.run(["xssstate", "-i"], capture_output=True, text=True, timeout=2).stdout)
            except (OSError, ValueError, subprocess.SubprocessError):
                self.idle = 0
            # ponytail: X reports idle time only when asked; once away, re-ask every 30 s to notice the return.
            self.idle_check = now + (30 if self.idle >= AWAY else (AWAY - self.idle) / 1000)
        return self.idle >= AWAY

    def tick(self, now):
        key = (self.current[1], clean(self.current[2])) if self.current else None
        if key and now - self.since >= self.dwell():
            verdict = "on_task" if key in self.allowed else self.judge(*self.current[1:])
            if self.verdict == "distraction" and verdict != "distraction":
                # The user said this window is for the task.
                self.session["drift"] = max(0, self.session["drift"] - self.window_drift.pop(key, 0))
                if self.nudged_key == key:
                    self.nudged_at = self.nudged_key = None
            self.verdict = verdict
            if verdict == "on_task":
                self.last_on_task = self.current[0]
        if self.session["status"] != self.judge.status or self.session["voice"] != self.judge.voice:
            self.session["status"] = self.judge.status
            self.session["voice"] = self.judge.voice
            self.save(refresh=True)
        if self.verdict == "distraction":
            spent = now - self.accounted
            self.session["drift"] += spent
            self.window_drift[key] = self.window_drift.get(key, 0) + spent
            if self.nudged_at is None:
                self.nudged_at, self.nudged_key = now, key
                self.session["nudges"] += 1
                self.notify(self.judge.line("nudge"),
                            f"{key[1][:80]}\nBack to: {self.judge.task}\nClick if this is for your task.", allow=key)
                self.save(refresh=True)
            elif now - max(self.nudged_at, self.since) >= GRACE:
                con_id = self.current[0]
                found = {item[0]: item[3:5] for item in windows()}
                if found.get(con_id, ("__i3_scratch",))[0] != "__i3_scratch":
                    self.hide(con_id, *found[con_id])
                    if self.last_on_task in found:
                        i3(f"[con_id={self.last_on_task}] focus")
                    self.notify(self.judge.line("hide"), f"{key[1][:80]}\nBack to: {self.judge.task}")
                    self.save(refresh=True)
                self.refocus()
        elif self.verdict == "neutral" and self.away(now):
            # ponytail: idle on an on-task window (reading, lecture) is trusted; only unproductive idle counts.
            if not self.session.get("away"):
                self.session["away"] = True
                self.accounted = now
                self.notify(self.judge.line("away"), f"Back to: {self.judge.task}")
            self.session["drift"] += now - self.accounted
        else:
            self.session.pop("away", None)
        if self.verdict is not None:
            self.accounted = now

    def run(self):
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self.save()
        events = subprocess.Popen(["i3-msg", "-t", "subscribe", "-m", '["window", "workspace"]'],
                                  stdout=subprocess.PIPE, text=True)
        stream = events.stdout.fileno()
        try:
            self.preblock()
            self.save()
            self.refocus()
            while self.running:
                now = time.monotonic()
                due = self.deadline(now)
                ready, _, _ = select.select([stream, self.wake_read], [], [], None if due is None else due - now)
                if self.wake_read in ready:
                    os.read(self.wake_read, 4096)
                if stream in ready:
                    # Any i3 event may change focus or the title; the payload itself is not needed.
                    if not os.read(stream, 65536):
                        break
                    self.refocus()
                now = time.monotonic()
                self.judge.unload(now)
                self.tick(now)
                self.save()
        finally:
            events.terminate()
            if self.verdict == "distraction" or self.session.get("away"):
                self.session["drift"] += time.monotonic() - self.accounted
            self.session["cheer"] = self.judge.line("done")
            self.session["bloom"] = self.judge.line("bloom")
            self.session["milestone"] = self.judge.line("milestone")
            self.save()
            restore(self.session)
            self.save()
            try:
                self.judge.save_memory()
            except OSError as error:
                print(f"Could not save focus memory: {error}", file=sys.stderr)

    def stop(self, *_):
        self.running = False
        self.poke()


def restore(session):
    """Return hidden windows to their workspaces. Floating ones (dropdowns) stay in the scratchpad."""
    found = {con_id: workspace for con_id, _app, _title, workspace, _floating, _focused in windows()}
    for item in session.get("hidden", []):
        if found.get(item["con"]) == "__i3_scratch" and not item["floating"]:
            i3(f"[con_id={item['con']}] scratchpad show, floating disable, "
               f"move container to workspace {json.dumps(item['workspace'])}")
    session["hidden"] = []


if __name__ == "__main__":
    if sys.argv[1:] == ["restore"]:
        path = STATE / "focus-guard.json"
        data = json.loads(path.read_text())
        restore(data)
        path.write_text(json.dumps(data))
    else:
        Guard().run()
