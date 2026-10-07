#!/usr/bin/env python3
"""Run with /usr/bin/python3 scripts/test-desktop-shortcuts.py; no desktop changes."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reply(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout, b"" if isinstance(stdout, bytes) else "")


capture = load("quick-task")
dropdown = load("dropdown-terminal")
launcher = load("project-launcher")
nemo = load("nemo-folder")
ocr = load("screenshot-text")
finder = load("shortcut-finder")
real_run = subprocess.run

with tempfile.TemporaryDirectory() as directory:
    data = Path(directory) / "tasks"
    data.mkdir()
    env = dict(os.environ, TASKRC="/dev/null", TASKDATA=str(data))
    entries = iter(['"unfinished', "Example due:not-a-real-date",
                    'Read "chapter 3" due:tomorrow project:Test +check $(touch NEVER)'])
    prompts = []
    notices = []

    def capture_run(args, **kwargs):
        if args[0] == "rofi":
            prompts.append(args)
            return reply(next(entries))
        if args[0] == "notify-send":
            notices.append(args)
            return reply()
        return real_run(args, env=env, **kwargs)

    with patch.object(capture.subprocess, "run", side_effect=capture_run):
        capture.main()
    tasks = json.loads(real_run(["/home/linuxbrew/.linuxbrew/bin/task", "export"],
                                env=env, capture_output=True, text=True, check=True).stdout)
    assert len(tasks) == 1 and "$(touch NEVER)" in tasks[0]["description"]
    assert tasks[0]["project"] == "Test" and "check" in tasks[0]["tags"] and tasks[0]["due"]
    assert len(prompts) == 3 and prompts[1][prompts[1].index("-filter") + 1] == '"unfinished'
    assert len(notices) == 1
    for result in [reply(code=1), reply("   ")]:
        with patch.object(capture.subprocess, "run", return_value=result) as run:
            capture.main()
            assert run.call_count == 1

    folder = Path(directory) / "project with spaces; literal"
    folder.mkdir()
    calls = []
    main_tree = {"type": "workspace", "num": 1, "nodes": [
        {"id": 42, "window": 100, "window_properties": {"class": "kitty"}}
    ]}

    def process_status(path, *args, **kwargs):
        parents = {201: 202, 202: 200, 301: 300, 300: 1}
        return f"PPid:\t{parents.get(int(path.parts[2]), 1)}\n"

    def launcher_run(args, **kwargs):
        calls.append(args)
        if args[0].endswith("zoxide"):
            return reply(str(folder) + "\n")
        if args[0] == "rofi":
            return reply("0\n")
        if args[0] == "i3-msg":
            return reply(json.dumps(main_tree) if "get_tree" in args else '[{"success":true}]')
        if args[0] == "xprop":
            return reply("_NET_WM_PID(CARDINAL) = 200")
        if args[1] == "list-clients":
            return reply("201\t$1\n301\t$2\n")
        return reply()

    with patch.object(launcher.subprocess, "run", side_effect=launcher_run), \
         patch.object(launcher.Path, "read_text", process_status), \
         patch.object(launcher.subprocess, "Popen") as launch:
        launcher.main()
        assert [launcher.TMUX, "new-window", "-t", "$1", "-c", str(folder)] in calls
        assert ["i3-msg", "[con_id=42] focus"] in calls
        launch.assert_not_called()
    for candidate in ({"nodes": []}, {"type": "workspace", "num": 1, "nodes": [
        {"id": 42, "window": 100, "window_properties": {"class": "kitty"}},
        {"id": 43, "window": 101, "window_properties": {"class": "kitty"}},
    ]}):
        calls.clear()

        def failed_target_run(args, **kwargs):
            if "get_tree" in args:
                return reply(json.dumps(candidate))
            if args[0] == "xprop" and args[2] == "101":
                return reply("_NET_WM_PID(CARDINAL) = 300")
            return launcher_run(args, **kwargs)

        with patch.object(launcher.subprocess, "run", side_effect=failed_target_run), \
             patch.object(launcher.Path, "read_text", process_status):
            try:
                launcher.main()
                raise AssertionError("Missing or ambiguous main terminal must be rejected")
            except RuntimeError as error:
                assert "one main tmux terminal" in str(error)
        assert not any("new-window" in args or "new-session" in args for args in calls)
    with patch.object(launcher.subprocess, "run", side_effect=[reply(str(folder)), reply(code=1)]), \
         patch.object(launcher.subprocess, "Popen") as launch:
        launcher.main()
        launch.assert_not_called()

    tree = {"nodes": [], "floating_nodes": [{"nodes": [
        {"id": 42, "window_properties": {"class": dropdown.CLASS}}
    ]}]}
    assert dropdown.find_window(tree) == 42
    assert dropdown.find_window({"nodes": []}) is None
    with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}), \
         patch.object(dropdown, "window_id", return_value=42), \
         patch.object(dropdown.subprocess, "Popen") as launch, \
         patch.object(dropdown.subprocess, "run", return_value=reply('[{"success":true}]')):
        dropdown.main()
        dropdown.main()
        launch.assert_not_called()
    with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}), \
         patch.object(dropdown, "window_id", side_effect=[None, 42]), \
         patch.object(dropdown.time, "sleep"), \
         patch.object(dropdown.subprocess, "Popen") as launch, \
         patch.object(dropdown.subprocess, "run", return_value=reply('[{"success":true}]')):
        dropdown.main()
        assert launch.call_count == 1
        assert launch.call_args.args[0][-6:] == ["-L", "dropdown", "new-session", "-A", "-s", "scratch"]
    with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}), \
         patch.object(dropdown.fcntl, "flock", side_effect=BlockingIOError), \
         patch.object(dropdown, "window_id") as lookup, \
         patch.object(dropdown.subprocess, "Popen") as launch:
        dropdown.main()
        lookup.assert_not_called()
        launch.assert_not_called()

with tempfile.TemporaryDirectory() as directory:
    home = Path(directory)
    nested = home / "course work; $(literal)" / "notes"
    nested.mkdir(parents=True)
    for excluded in (".hidden", "node_modules", "target", "venv", "__pycache__", "build", "dist"):
        (home / excluded / "nested").mkdir(parents=True)
    (home / "link").symlink_to(nested, target_is_directory=True)
    (home / "go" / "pkg" / "mod").mkdir(parents=True)
    (nested / "loop").symlink_to(home, target_is_directory=True)
    document = nested / "Lecture.PDF"
    document.write_text("Document test")
    (home / "todo.md").write_text("Notes")
    (home / ".hidden" / "hidden.pdf").write_text("Excluded")
    (home / "target" / "generated.pdf").write_text("Excluded")
    (home / "photo.png").write_text("Not a document")
    paths = real_run(nemo.scan_command(), cwd=home, capture_output=True,
                     text=True, check=True).stdout.splitlines()
    assert set(paths) == {"~/", "~/course work; $(literal)", "~/course work; $(literal)/notes",
                          "~/course work; $(literal)/notes/loop", "~/link", "~/go"}
    assert paths.index("~/go") < paths.index("~/course work; $(literal)/notes")
    documents = real_run(nemo.scan_command(documents=True), cwd=home,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    assert set(documents) == {"~/todo.md", "~/course work; $(literal)/notes/Lecture.PDF"}
    real_popen = subprocess.Popen
    scans = []

    def start_scan(*args, **kwargs):
        if args[0][0] in ("nemo", "xdg-open"):
            calls.append(args[0])
            return None
        process = real_popen(*args, **kwargs)
        scans.append(process)
        return process

    for selection in (reply("~/course work; $(literal)/notes\n"), reply(code=1), reply("~/deleted\n")):
        calls = []

        def menu_run(args, **kwargs):
            calls.append(args)
            return selection if args[0] == "rofi" else reply()

        with patch.object(nemo.Path, "home", return_value=home), \
             patch.object(nemo.subprocess, "Popen", side_effect=start_scan), \
             patch.object(nemo.subprocess, "run", side_effect=menu_run):
            try:
                nemo.main()
                assert selection.stdout != "~/deleted\n"
            except RuntimeError as error:
                assert selection.stdout == "~/deleted\n" and "no longer exists" in str(error)
        assert scans[-1].poll() is not None
        launches = [args for args in calls if args[0] == "nemo"]
        assert launches == ([["nemo", str(nested)]] if selection.stdout.startswith("~/course") else [])

    calls = []
    with patch.object(nemo.Path, "home", return_value=home), \
         patch.object(nemo.subprocess, "Popen", side_effect=start_scan), \
         patch.object(nemo.subprocess, "run", return_value=reply("~/course work; $(literal)/notes/Lecture.PDF\n")):
        nemo.main(documents=True)
    assert calls == [["xdg-open", str(document)]] and scans[-1].poll() is not None

    sample = home / "ocr.png"
    real_run(["convert", "-size", "900x140", "xc:white", "-font", "DejaVu-Sans",
              "-pointsize", "48", "-fill", "black", "-gravity", "center", "-annotate", "0",
              "Clipboard OCR check", str(sample)], check=True)
    copied = []

    def ocr_run(args, **kwargs):
        if args[0] == "flameshot":
            return reply(sample.read_bytes())
        if args[0] == "xclip":
            copied.append(kwargs["input"])
            return reply()
        if args[0] == "notify-send":
            return reply()
        return real_run(args, **kwargs)

    with patch.object(ocr.subprocess, "run", side_effect=ocr_run):
        ocr.main()
    assert copied == [b"Clipboard OCR check"]
    with patch.object(ocr.subprocess, "run", return_value=reply(b"", code=1)) as run:
        ocr.main()
        assert run.call_count == 1
    with patch.object(ocr.subprocess, "run", side_effect=[reply(b"PNG"), reply(b""), reply()]) as run:
        ocr.main()
        assert not any(call.args[0][0] == "xclip" for call in run.call_args_list)
    with patch.object(ocr.subprocess, "run", side_effect=[reply(b"PNG"), reply(b"", code=2)]) as run:
        try:
            ocr.main()
            raise AssertionError("Recognition error must be reported")
        except RuntimeError:
            assert run.call_count == 2

rows = finder.shortcuts('''set $mod Mod4
# shortcut: Open terminal
bindsym $mod+Return exec kitty
mode "resize" {
    # shortcut: Shrink width
    bindsym h resize shrink width 10 px
}
bindsym --release $mod+F2 exec \\
    echo fallback
''')
assert rows == ["Super+Enter — Open terminal", "Resize mode: h — Shrink width",
                "Super+F2 — exec echo fallback"]
config = Path(__file__).resolve().parents[1] / "i3/config"
current_rows = finder.shortcuts(config.read_text())
assert "Super+Print — Screenshot to text" in current_rows
assert "Super+Ctrl+p — Find document" in current_rows
with patch.object(finder.Path, "read_text", return_value=config.read_text()), \
     patch.object(finder.subprocess, "run", side_effect=[reply("0"), reply()]) as run:
    finder.main()
    assert [call.args[0][0] for call in run.call_args_list] == ["rofi", "notify-send"]

print("Desktop shortcut checks passed")
