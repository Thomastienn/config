#!/usr/bin/env python3
"""Behavior checks for command alerts, PDF results, audio routing and mode cleanup."""

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import afk
import pdf_search


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alerts = load("command-finished")
controls = load("desktop-controls")


class Productivity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, XDG_RUNTIME_DIR=str(self.root / "run"),
                         XDG_STATE_HOME=str(self.root / "state"), XDG_CONFIG_HOME=str(self.root / "config"))
        env.start()
        self.addCleanup(env.stop)

    def test_alert_privacy_and_suppression(self):
        with patch.object(alerts, "pane_focused", return_value=False), \
             patch.object(alerts, "output", return_value="main:2.1"), \
             patch.object(alerts.subprocess, "run") as run:
            alerts.main(7, 125, 1, 'TOKEN=private cargo test --password "secret"')
            message = " ".join(run.call_args.args[0])
            self.assertIn("cargo failed (exit 7)", message)
            self.assertNotIn("secret", message)
            self.assertNotIn("private", message)
            run.reset_mock()
            for status, duration, command in [(130, 60, "cargo build"), (0, 29, "make"), (0, 120, "nvim notes")]:
                alerts.main(status, duration, 1, command)
            run.assert_not_called()
        with patch.object(alerts, "pane_focused", return_value=True), patch.object(alerts.subprocess, "run") as run:
            alerts.main(0, 60, 1, "cargo build")
            run.assert_not_called()

    def test_tmux_other_tab_and_other_terminal(self):
        def output(args):
            if "_NET_ACTIVE_WINDOW" in args:
                return "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x100"
            if "_NET_WM_PID" in args:
                return "_NET_WM_PID(CARDINAL) = 42"
            return "100\t%1\n200\t%2"
        with patch.object(alerts, "output", side_effect=output), \
             patch.object(alerts, "ancestors", side_effect=lambda pid: {42, 100} if pid == 100 else {43, 200}):
            self.assertTrue(alerts.pane_focused(99, "%1"))
            self.assertFalse(alerts.pane_focused(99, "%2"))
            self.assertFalse(alerts.pane_focused(99, "%3"))

    def test_shell_hook_preserves_status(self):
        script = 'blehook() { :; }; source "$1"; desktop_command_begin "false"; (exit 7); desktop_command_end; exit $?'
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", script, "check",
                                 str(Path(__file__).with_name("command-finished.sh"))])
        self.assertEqual(result.returncode, 7)

    def test_decimal_active_window(self):
        with patch.object(alerts, "output", side_effect=["_NET_ACTIVE_WINDOW(CARDINAL) = 256",
                                                         "_NET_WM_PID(CARDINAL) = 42"]), \
             patch.object(alerts, "ancestors", return_value={42, 99}):
            self.assertTrue(alerts.pane_focused(99, ""))

    def test_long_command_hook_is_quiet_and_preserves_status(self):
        script = ('blehook() { :; }; source "$1"; desktop_command_begin "nvim"; '
                  'SECONDS=$((SECONDS+31)); (exit 9); desktop_command_end; result=$?; '
                  'test -z "$(jobs -p)" || exit 55; exit "$result"')
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", script, "check",
                                 str(Path(__file__).with_name("command-finished.sh"))], capture_output=True, text=True)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(result.stdout + result.stderr, "")

    def test_pdf_encoded_paths_and_deleted_results(self):
        document = self.root / "lecture #?%20 space; $(literal).PDF"
        document.touch()
        rows = ["Recoll query: something", "3 results", base64.b64encode(("file://" + str(document)).encode()).decode(),
                base64.b64encode(("file://" + str(self.root / "missing.pdf")).encode()).decode(),
                base64.b64encode(b"https://example.com/a.pdf").decode()]
        reply = subprocess.CompletedProcess([], 0, "\n".join(rows), "")
        with patch.object(pdf_search.subprocess, "run", return_value=reply), \
             patch.object(pdf_search.Path, "home", return_value=self.root):
            self.assertEqual(pdf_search.search("normalization"), [document])

    def test_microphone_switch_preserves_monitor_capture(self):
        calls = []
        sources = [{"index": 1, "name": "old-mic"}, {"index": 2, "name": "new-mic"}]
        def capture(args):
            calls.append(args)
            if args[-1] == "source-outputs":
                return json.dumps([{"index": 10, "source": 1}, {"index": 11, "source": 99}])
            return ""
        with patch.object(controls, "audio_devices", return_value=([], sources)), \
             patch.object(controls, "capture", side_effect=capture):
            controls.switch_audio("input", 2)
            self.assertIn(["pactl", "set-default-source", "new-mic"], calls)
            self.assertIn(["pactl", "move-source-output", "10", "new-mic"], calls)
            self.assertFalse(any("11" in row for row in calls))
            calls.clear()
            with self.assertRaises(RuntimeError):
                controls.switch_audio("input", 999)
            self.assertEqual(calls, [])

    def test_focus_restores_owned_pause_and_preserves_manual_change(self):
        for current, restores in [(50, True), (100, False)]:
            controls.write_json(controls.focus_path(), {"mode": "focus", "pause_before": 0, "pause_set": 50})
            with patch.object(controls, "capture", return_value=str(current)) as capture:
                controls.focus_reset(done=True)
                self.assertEqual(capture.call_count, 2 if restores else 1)
            state = controls.read_json(controls.focus_path(), {})
            self.assertEqual(state["mode"], "done")
            self.assertNotIn("pause_set", state)
            with patch.object(controls, "capture") as capture:
                controls.focus_reset(done=True)
                capture.assert_not_called()

    def test_cancelled_focus_does_not_stop_existing_session(self):
        with patch.object(controls, "prompt", return_value=None), patch.object(controls, "capture") as capture:
            controls.focus_start(10)
            capture.assert_not_called()

    def test_break_keeps_previous_focus_duration(self):
        controls.write_json(controls.focus_path(), {"mode": "done", "task": "Read one section", "focus_minutes": 25})
        with patch.object(controls, "capture"):
            controls.focus_start(5, "break", ask=False)
            self.assertEqual(controls.read_json(controls.focus_path(), {})["focus_minutes"], 25)
            controls.main(["focus-continue"])
            self.assertEqual(controls.read_json(controls.focus_path(), {})["minutes"], 25)

    def test_saved_thought_is_literal_and_survives_session(self):
        note = 'Check $(touch NEVER); "later"\nsecond line'
        with patch.object(controls, "prompt", return_value=note):
            controls.main(["park"])
        self.assertEqual(controls.read_json(controls.notes_path(), []), [note])
        controls.focus_reset()
        self.assertEqual(controls.read_json(controls.notes_path(), []), [note])

    def test_afk_cleanup_and_closed_lid(self):
        state = afk.snapshot("timeout: 600 cycle: 300\nStandby: 100 Suspend: 200 Off: 300\nDPMS is Enabled")
        state.update(active=True, pid=os.getpid())
        afk.save(state)
        with patch.object(afk, "lid_open", return_value=False):
            self.assertFalse(afk.active())
        with patch.object(afk, "idle_control") as idle, patch.object(afk, "command") as command:
            afk.reset()
            idle.assert_called_once_with("Enable")
            self.assertIn(["xset", "s", "600", "300"], [call.args[0] for call in command.call_args_list])
            self.assertIn(["xset", "+dpms"], [call.args[0] for call in command.call_args_list])
        self.assertEqual(afk.read_state(), {})

    def test_afk_restore_attempts_all_settings_after_error(self):
        state = afk.snapshot("timeout: 600 cycle: 300\nStandby: 100 Suspend: 200 Off: 300\nDPMS is Enabled")
        state.update(active=True, pid=os.getpid())
        afk.save(state)
        with patch.object(afk, "idle_control", side_effect=OSError("socket unavailable")), \
             patch.object(afk, "command") as command:
            with self.assertRaises(RuntimeError):
                afk.reset()
            self.assertEqual(command.call_count, 4)
        self.assertFalse(afk.read_state()["active"])


if __name__ == "__main__":
    unittest.main()
