#!/usr/bin/env python3
"""Lock-in guard for one focus session: judge the focused window, nudge, hide, and measure drift.

Runs only while thomas-focus.service is in focus mode. Chosen windows and exact Brave
pages govern access; Decima supplies local content feedback during approval. The loop
sleeps until an i3/browser event, prompt response, or deadline. 9router only writes
session themes and notification/reward wording; it never controls access or credit.
"""

import ctypes
import gc
import html
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

import focus_browser as browser

STATE = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "thomas-desktop"
RULES_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "thomas-desktop/focus-rules.json"
MODEL = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "thomas-desktop/decima-small/onnx/int8"
MEMORY = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "thomas-desktop/focus-verdicts.json"
VOICE = MEMORY.with_name("focus-voice.json")
ROUTER = "http://127.0.0.1:20128/v1/chat/completions"
CONTROLS = Path(__file__).with_name("desktop-controls.py")

DWELL = 2       # unapproved windows stop earning immediately, then hide after two seconds
CHECK_IN = 300
APPROVAL = 300
FRICTION = 10
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
    transient = {}
    def walk(node, workspace, floating):
        if node.get("type") == "workspace":
            workspace = node["name"]
        if node.get("window"):
            transient[node["id"]] = (node["window"], (node.get("window_properties") or {}).get("transient_for"))
            yield (node["id"], (node.get("window_properties") or {}).get("class") or "", node.get("name") or "",
                   workspace, floating, node.get("focused", False))
        for child in node.get("nodes", []):
            yield from walk(child, workspace, floating)
        for child in node.get("floating_nodes", []):
            yield from walk(child, workspace, True)
    tree = json.loads(subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True, text=True, timeout=5).stdout)
    result = list(walk(tree, "", False))
    windows.transient = transient
    return result


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
        self.focus = json.loads((STATE / "focus.json").read_text())
        self.session = {"id": self.focus["id"], "strict": True, "drift": 0.0, "waiting": 0.0,
                        "focused": 0.0, "nudges": 0, "checkins": 0, "hidden": [],
                        "attention": "working", "status": "Lock-in on", "failure": ""}
        self.wake_read, self.wake_write = os.pipe()
        os.set_blocking(self.wake_write, False)
        self.judge = Judge(self.focus["task"], self.focus["track"], self.poke)
        self.session["voice"] = self.judge.voice
        self.work = {key: self.focus.get("work_xids", {}).get(str(key)) for key in self.focus["work_windows"]}
        self.temporary = {}
        self.temporary_xids = {}
        self.connection = browser.subscribe()
        self.buffer = b""
        self.activity = browser.request("status")
        if self.activity.get("session") != self.session["id"]:
            raise RuntimeError("Browser session was not acknowledged")
        self.current = None
        self.last_on_task = next(iter(self.work), None)
        self.last_blocked = self.last_blocked_xid = None
        self.since = self.accounted = self.focus["started"]
        self.bucket = "waiting"
        self.next_check = self.focus["started"] + CHECK_IN
        self.phase = "working"
        self.prompt = self.prompt_kind = self.target = None
        self.wait_until = None
        self.step = self.focus["task"]
        self.running = True

    def poke(self):
        try:
            os.write(self.wake_write, b".")
        except BlockingIOError:
            pass

    def account(self, now):
        until = min(now, self.focus["deadline"])
        spent = max(0, until - self.accounted)
        field = {"working": "focused", "waiting": "waiting", "distraction": "drift"}[self.bucket]
        self.session[field] += spent
        self.accounted = max(self.accounted, until)

    def save(self, refresh=False):
        snapshot = dict(self.session, accounted=self.accounted, voice=self.judge.voice, attention=self.phase)
        elapsed = int(sum(self.session[key] for key in ("drift", "waiting", "focused")))
        for key in ("drift", "focused"):
            snapshot[key] = int(self.session[key])
        snapshot["waiting"] = elapsed - snapshot["drift"] - snapshot["focused"]
        snapshot["can_approve"] = self.last_blocked is not None
        snapshot["needs_checkin"] = self.phase == "checkin" and self.prompt is None
        descriptor, temporary = tempfile.mkstemp(prefix=".focus-guard-", dir=STATE)
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(snapshot, output)
            os.replace(temporary, STATE / "focus-guard.json")
        finally:
            Path(temporary).unlink(missing_ok=True)
        visible = (snapshot["status"], self.phase, snapshot["needs_checkin"], snapshot["can_approve"],
                   snapshot["drift"] // 60, snapshot["waiting"] // 60, tuple(snapshot["voice"].items()))
        if refresh and visible != getattr(self, "last_ui", None):
            self.last_ui = visible
            subprocess.Popen(["/usr/bin/python3", str(CONTROLS), "focus-refresh"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def notify(self, title, body):
        subprocess.Popen(["notify-send", "-a", "Focus", "-t", "10000", title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def hide(self, item):
        con_id, _app, _title, workspace, floating, _focused = item
        if workspace == "__i3_scratch":
            return
        i3(f"[con_id={con_id}] move scratchpad")
        if not any(hidden["con"] == con_id for hidden in self.session["hidden"]):
            self.session["hidden"].append({"con": con_id, "workspace": workspace, "floating": floating,
                                           "xid": getattr(windows, "transient", {}).get(con_id, (None, None))[0]})

    def is_work(self, item, now):
        con_id, app, title = item[:3]
        if con_id in self.work or self.temporary.get(con_id, 0) > now:
            return True
        if "brave" in app.lower():
            return self.activity.get("allowed", False) and clean(title) == clean(self.activity.get("title", ""))
        relatives = getattr(windows, "transient", {})
        parent = relatives.get(con_id, (None, None))[1]
        return parent is not None and any(value[0] == parent and (key in self.work or self.temporary.get(key, 0) > now)
                                          for key, value in relatives.items())

    def utility(self, item):
        return any(name in item[1].lower() for name in ("rofi", "eww", "pavucontrol", "blueman", "pinentry", "polkit"))

    def paired(self):
        return (self.current and "brave" in self.current[1].lower()
                and clean(self.current[2]) == clean(self.activity.get("title", "")))

    def refocus(self, now):
        self.account(now)
        items = windows()
        live = {item[0] for item in items}
        identities = getattr(windows, "transient", {})
        self.work = {key: xid for key, xid in self.work.items() if key in live and identities.get(key, (None, None))[0] == xid}
        self.temporary = {key: until for key, until in self.temporary.items() if key in live and until > now
                          and identities.get(key, (None, None))[0] == self.temporary_xids.get(key)}
        current = next((item for item in items if item[5]), None)
        if current != self.current:
            self.current = current
            self.since = now
        if self.phase != "working" or not current or self.utility(current):
            self.bucket = "waiting"
        elif self.is_work(current, now):
            self.bucket = "working"
            self.last_on_task = current[0]
        else:
            self.bucket = "distraction"
            self.last_blocked = current
            self.last_blocked_xid = identities.get(current[0], (None, None))[0]
        working = {"working": "Working on chosen resources", "waiting": "Waiting for chosen work · credit paused",
                   "distraction": "Outside chosen work · no credit"}[self.bucket]
        self.session["status"] = {"working": working, "checkin": "Check-in needed · credit paused",
                                  "approval": "Approving access · credit paused", "ending": "Ending session · credit paused"}[self.phase]
        if self.wait_until:
            self.session["status"] += " · 10-second wait"
        if self.phase == "approval" and self.target and self.target.get("category"):
            self.session["status"] += " · " + self.target["category"]

    def ask(self, kind):
        if self.prompt is not None:
            return
        if kind == "checkin":
            question = "Recall one idea, or type /stuck" if self.focus["track"] == "study" else "One concrete change or next action, or /stuck"
        elif kind == "next_step":
            question = "What is one smaller, two-minute next step?"
        elif kind == "reason":
            question = "How will this resource help your task?"
        else:
            question = "Why end this session?"
        context = question + "\n" + self.step
        if kind == "reason" and self.target:
            context += "\nResource: " + self.target.get("title", "Hidden desktop window")
        heading = {"checkin": "Check-in", "next_step": "Smaller step", "reason": "Approve access", "end": "End session"}[kind]
        args = ["rofi", "-dmenu", "-p", heading, "-format", "s" if kind == "end" else "f",
                "-lines", "3" if kind == "end" else "0", "-kb-custom-1", "Alt+Escape",
                "-mesg", html.escape(context) + "\nAlt+Escape: emergency end now. Esc: dismiss; credit stays paused."]
        if kind == "end":
            args += ["-no-custom", "-sync"]
        self.prompt = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.prompt.stdin.write(b"Need a break\nDone for now\nSomething else\n" if kind == "end" else b"")
        self.prompt.stdin.close()
        self.prompt_kind = kind

    def clear_prompt(self):
        if self.prompt is not None:
            if self.prompt.poll() is None:
                self.prompt.terminate()
            self.prompt.wait(timeout=2)
            self.prompt.stdout.close()
            self.prompt = None

    def emergency(self):
        self.session["exit_reason"] = "emergency"
        self.running = False
        os.kill(os.getppid(), signal.SIGTERM)

    def control(self, action, now):
        self.account(now)
        if action == "resume":
            if self.phase == "checkin":
                self.ask("checkin")
            elif self.phase in ("approval", "ending"):
                self.clear_prompt()
                self.phase, self.target, self.wait_until = "working", None, None
        elif action == "approve_window" and self.last_blocked and self.phase == "working":
            # Browser access must pass through the extension, never a whole-window exception.
            if any(name in self.last_blocked[1].lower() for name in BROWSERS):
                return
            self.target = {"window": self.last_blocked[0], "title": self.last_blocked[2], "app": self.last_blocked[1],
                           "xid": self.last_blocked_xid}
            self.phase = "approval"
            self.ask("reason")
        elif action == "end":
            self.clear_prompt()
            self.phase, self.target, self.wait_until = "ending", None, None
            self.ask("end")
        self.refocus(now)
        browser.request("ui", session=self.session["id"], message="" if self.phase == "working" else self.session["status"])
        self.save(refresh=True)

    def answer(self, now):
        self.account(now)
        result = self.prompt.stdout.read(4096).decode(errors="replace").strip()[:300]
        code = self.prompt.wait(timeout=2)
        kind = self.prompt_kind
        self.clear_prompt()
        if code == 10:
            self.emergency()
            return
        if code != 0 or not result:
            if self.phase != "checkin":
                self.phase, self.target = "working", None
            self.refocus(now)
            self.save(refresh=True)
            return
        if kind == "checkin" and result.lower() == "/stuck":
            self.ask("next_step")
            return
        if kind in ("checkin", "next_step"):
            if kind == "next_step":
                self.step = result
            self.session["checkins"] += 1
            self.phase = "working"
            self.next_check = now + CHECK_IN
        else:
            self.wait_until = now + FRICTION
            self.session["status"] = "10-second wait · use Focus to cancel; emergency end is immediate"
            browser.request("ui", session=self.session["id"], message=self.session["status"])
        # The typed response is never saved or sent to a provider.
        self.refocus(now)
        self.save(refresh=True)

    def browser_events(self, now):
        data = self.connection.recv(65536)
        if not data:
            raise RuntimeError("Brave bridge disconnected; session ended")
        self.buffer += data
        if len(self.buffer) > browser.LIMIT:
            raise ValueError("Browser event is too large")
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            event = json.loads(raw)
            if event.get("session") != self.session["id"]:
                continue
            self.account(now)
            if event.get("event") == "activity":
                self.activity = event
            elif event.get("event") == "approval" and self.phase == "working":
                from urllib.parse import urlsplit
                if urlsplit(str(event.get("url", ""))).scheme not in ("http", "https"):
                    continue
                self.target = {"url": event["url"], "title": str(event.get("title", ""))[:300]}
                self.phase = "approval"
                # Classification is informative; approval is always explicit.
                self.judge("Brave", str(event.get("title", ""))[:300])
                self.ask("reason")
            elif event.get("event") == "emergency":
                self.emergency()
            elif event.get("event") == "expired":
                if now < self.focus["deadline"] - 1:
                    raise RuntimeError("Browser enforcement ended unexpectedly")
            elif event.get("event") == "control":
                self.control(event.get("action"), now)
        self.refocus(now)

    def tick(self, now):
        self.account(now)
        if self.phase == "approval" and self.target and "title" in self.target:
            category = self.judge(self.target.get("app", "Brave"), self.target["title"])
            if category:
                self.target["category"] = {"on_task": "work content", "distraction": "entertainment", "neutral": "uncertain content"}[category]
        if self.wait_until is not None and now >= self.wait_until:
            if self.phase == "ending":
                self.session["exit_reason"] = "requested"
                self.running = False
                os.kill(os.getppid(), signal.SIGTERM)
                return
            if self.target and "url" in self.target:
                browser.request("approve", session=self.session["id"], url=self.target["url"])
            elif self.target:
                con_id = self.target["window"]
                live = windows()
                identity = getattr(windows, "transient", {}).get(con_id, (None, None))[0]
                if any(item[0] == con_id for item in live) and identity == self.target.get("xid"):
                    self.temporary[con_id] = now + APPROVAL
                    self.temporary_xids[con_id] = identity
                    owned = next((item for item in self.session["hidden"] if item["con"] == con_id), None)
                    if owned and not owned["floating"]:
                        restore({"hidden": [owned]})
                    i3(f"[con_id={con_id}] scratchpad show" if owned and owned["floating"] else f"[con_id={con_id}] focus")
            self.phase, self.wait_until, self.target = "working", None, None
            browser.request("ui", session=self.session["id"], message="")
        if self.phase == "working" and self.next_check <= now < self.focus["deadline"]:
            self.phase = "checkin"
            self.ask("checkin")
        self.refocus(now)
        if self.bucket == "distraction" and now - self.since >= DWELL and self.current:
            # Paired Brave pages are gated inside the browser, preserving work tabs.
            if not self.paired():
                self.hide(self.current)
                self.session["nudges"] += 1
                if self.last_on_task:
                    i3(f"[con_id={self.last_on_task}] focus")
                self.notify(self.judge.line("hide"), "Unapproved window tucked away. Open Focus to request five minutes.")
                self.refocus(now)
        self.judge.unload(now)

    def deadline(self, now):
        due = [self.focus["deadline"]]
        if self.phase == "working":
            due.append(self.next_check)
        if self.wait_until:
            due.append(self.wait_until)
        if self.bucket == "distraction" and self.current and not self.paired():
            due.append(self.since + DWELL)
        due.extend(self.temporary.values())
        if self.judge.model:
            due.append(self.judge.used + UNLOAD)
        return min((value for value in due if value > now), default=None)

    def run(self):
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        events = subprocess.Popen(["i3-msg", "-t", "subscribe", "-m", '["window", "workspace"]'], stdout=subprocess.PIPE)
        stream = events.stdout.fileno()
        try:
            self.refocus(time.monotonic())
            for item in windows():
                if rule(item[1], "", self.judge.table) == "distraction" and item[0] not in self.work:
                    self.hide(item)
            self.save(refresh=True)
            print("ready", flush=True)
            while self.running:
                now = time.monotonic()
                due = self.deadline(now)
                watching = [stream, self.wake_read, self.connection]
                if self.prompt:
                    watching.append(self.prompt.stdout.fileno())
                ready, _, _ = select.select(watching, [], [], None if due is None else max(0, due - now))
                now = time.monotonic()
                self.account(now)
                if self.wake_read in ready:
                    os.read(self.wake_read, 4096)
                if stream in ready:
                    if not os.read(stream, 65536):
                        raise RuntimeError("i3 disconnected; session ended")
                    self.refocus(now)
                if self.connection in ready:
                    self.browser_events(now)
                if not self.running:
                    break
                if self.prompt and self.prompt.stdout.fileno() in ready:
                    self.answer(now)
                self.tick(now)
                self.save(refresh=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            self.session["failure"] = str(error)
            self.bucket = "waiting"
            self.notify("Lock In ended", str(error))
            raise
        finally:
            self.account(time.monotonic())
            self.clear_prompt()
            events.terminate()
            events.wait(timeout=2)
            for kind, field in (("done", "cheer"), ("bloom", "bloom"), ("milestone", "milestone")):
                self.session[field] = self.judge.line(kind)
            self.save()
            try:
                browser.request("stop", session=self.session["id"])
            except (OSError, ValueError, RuntimeError):
                pass
            try:
                restore(self.session)
            finally:
                self.save()
                self.connection.close()
                os.close(self.wake_read)
                os.close(self.wake_write)
                self.judge.save_memory()

    def stop(self, *_):
        self.running = False
        self.poke()


def restore(session):
    """Return hidden windows to their workspaces. Floating ones (dropdowns) stay in the scratchpad."""
    found = {con_id: workspace for con_id, _app, _title, workspace, _floating, _focused in windows()}
    for item in session.get("hidden", []):
        same_window = ("xid" not in item or getattr(windows, "transient", {}).get(item["con"], (None, None))[0] == item["xid"])
        if found.get(item["con"]) == "__i3_scratch" and not item["floating"] and same_window:
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
