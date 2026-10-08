#!/usr/bin/env python3
"""Regression check for existing windows switching into and out of i3 tabs."""

from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

from Xlib import Xatom

update_hints = runpy.run_path(str(Path(__file__).with_name("i3-frame-hints.py")))["update_hints"]
connection = MagicMock()
frame = MagicMock()
frame.get_wm_class.return_value = ("i3-frame", "i3-frame")
client = MagicMock()
client.id = 42
geometry = SimpleNamespace(y=2)
client.get_geometry.return_value = geometry
frame.query_tree.return_value.children = [client]
connection.screen.return_value.root.query_tree.return_value.children = [frame]

previous = update_hints(connection, {})
client.change_property.assert_called_once_with(ANY, Xatom.CARDINAL, 32, [0])
client.change_property.reset_mock()

geometry.y = 0
previous = update_hints(connection, previous)
client.change_property.assert_called_once_with(ANY, Xatom.CARDINAL, 32, [1])
client.change_property.reset_mock()

previous = update_hints(connection, previous)
client.change_property.assert_not_called()

geometry.y = 2
update_hints(connection, previous)
client.change_property.assert_called_once_with(ANY, Xatom.CARDINAL, 32, [0])
print("PASS: the same window updates its corner hint across tab layout changes.")
