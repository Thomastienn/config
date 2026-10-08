#!/usr/bin/env python3
"""Run with /usr/bin/python3 scripts/test-dropdown-browser.py; no desktop changes."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("dropdown_browser", Path(__file__).with_name("dropdown-browser.py"))
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


def window(target, role="browser", marks=(), window_class=browser.CLASS):
    return {"id": target, "window": target + 100, "marks": list(marks),
            "window_properties": {"class": window_class, "window_role": role}}


ordinary = window(10, marks=(browser.MARK,), window_class="Brave-browser")
scratch = window(20, marks=(browser.MARK, "another-mark"))
tree = {"nodes": [ordinary, window(30, role="pop-up")], "floating_nodes": [
    {"name": "__i3_scratch", "floating_nodes": [{"nodes": [scratch]}]},
]}
assert set(browser.browser_windows(tree)) == {20}
assert not browser.browser_windows(window(40, window_class=None))
assert set(browser.browser_windows(window(50, window_class="Firefox"))) == {50}

# Close shortcuts hide the marked browser, targeting its original container only.
scratch["focused"] = True
with patch.object(browser, "get_tree", return_value=tree), \
        patch.object(browser, "command") as command, \
        patch.object(browser.subprocess, "Popen") as launch:
    browser.close_focused()
    command.assert_called_once_with("[con_id=20] move scratchpad")
    launch.assert_not_called()
scratch["focused"] = False

# Ordinary Firefox and other applications still close; hidden scratch stays alive.
for window_class in ("firefox", "kitty"):
    ordinary_focused = window(60, window_class=window_class)
    ordinary_focused["focused"] = True
    close_tree = {"nodes": [{"nodes": [ordinary_focused]}], "floating_nodes": [scratch]}
    with patch.object(browser, "get_tree", return_value=close_tree), \
            patch.object(browser, "command") as command:
        browser.close_focused()
        command.assert_called_once_with("[con_id=60] kill")

with patch.object(browser, "get_tree", return_value={}), \
        patch.object(browser, "command") as command:
    browser.close_focused()
    command.assert_not_called()

with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
    # Reuse the marked browser, whether it is visible or hidden; preserve its geometry.
    with patch.object(browser, "get_windows", return_value={20: scratch}), \
            patch.object(browser, "command") as command, \
            patch.object(browser.subprocess, "Popen") as launch:
        browser.main()
        browser.main()
        assert [call.args[0] for call in command.call_args_list] == [
            "[con_id=20] scratchpad show", "[con_id=20] scratchpad show"]
        launch.assert_not_called()

    # Use the normal Firefox startup; no URL or new/private profile is forced.
    with patch.object(browser, "get_windows", side_effect=[{}, {}, {20: window(20)}]), \
            patch.object(browser.time, "sleep"), \
            patch.object(browser, "command") as command, \
            patch.object(browser.subprocess, "Popen") as launch:
        launch.return_value.poll.return_value = 0
        browser.main()
        launch.assert_called_once_with(["firefox"], start_new_session=True)
        assert all(call.args[0].startswith("[con_id=20]") for call in command.call_args_list)
        assert "move scratchpad" in command.call_args_list[0].args[0]
        assert "scratchpad show, resize set" in command.call_args_list[1].args[0]

    restored = window(21)
    restored["focused"] = True
    with patch.object(browser, "get_windows", side_effect=[{}, {20: window(20), 21: restored}]), \
            patch.object(browser.time, "sleep"), \
            patch.object(browser, "command") as command, \
            patch.object(browser.subprocess, "Popen"):
        browser.main()
        assert all(call.args[0].startswith("[con_id=21]") for call in command.call_args_list)

    with patch.object(browser, "get_windows", return_value={}), \
            patch.object(browser.time, "sleep"), \
            patch.object(browser, "command") as command, \
            patch.object(browser.subprocess, "Popen") as launch:
        launch.return_value.poll.return_value = 0
        try:
            browser.main()
            raise AssertionError("Missing new windows must time out")
        except RuntimeError as error:
            assert "ten seconds" in str(error)
        launch.assert_called_once()
        command.assert_not_called()

    with patch.object(browser.fcntl, "flock", side_effect=BlockingIOError), \
            patch.object(browser, "get_windows") as lookup, \
            patch.object(browser.subprocess, "Popen") as launch:
        browser.main()
        lookup.assert_not_called()
        launch.assert_not_called()

with patch.object(browser.subprocess, "run", return_value=subprocess.CompletedProcess(
        [], 0, '[{"success":false}]', "")):
    try:
        browser.command("[con_id=20] scratchpad show")
        raise AssertionError("i3 command failures must be reported")
    except RuntimeError:
        pass

finder_spec = importlib.util.spec_from_file_location("shortcut_finder", Path(__file__).with_name("shortcut-finder.py"))
finder = importlib.util.module_from_spec(finder_spec)
finder_spec.loader.exec_module(finder)
rows = finder.shortcuts((Path(__file__).resolve().parents[1] / "i3/config").read_text())
assert "Super+g — Browser scratchpad (Firefox)" in rows
assert "Super+` — Dropdown terminal" in rows
assert "Super+q — Close window or hide browser scratchpad" in rows
assert "Super+Shift+q — Close window or hide browser scratchpad" in rows
print("Firefox profile reuse, session launch, close-to-hide, window reuse, failures and shortcuts passed")
