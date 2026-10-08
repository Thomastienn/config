"""Run with: python3 conky/test_task_list.py."""

from pathlib import Path
import re
import runpy

module = runpy.run_path(str(Path(__file__).with_name("task_list.py")))
render = module["render"]
report = ("\x1b[4mDue   Date       Description\x1b[0m\n"
          "\x1b[38;5;5m-4mo  2026-05-20 Overdue task\x1b[0m\n"
          "\x1b[38;5;9;48;5;0m 1d   2026-10-09 Upcoming task\x1b[0m\n"
          " 7d   2026-10-15 Literal $5 and ${exec touch /tmp/example}\n")
output = render(report)
assert "${color #957FB8}-4mo  2026-05-20" in output
assert "${color #EC818C} 1d   2026-10-09" in output
assert "Literal $$5 and $${exec touch /tmp/example}" in output
assert "\x1b" not in output
assert re.sub(r"\$\{(?:color|font|hr)[^}]*\}", "", output).splitlines()[2].startswith("-4mo")
assert render("") == "No pending tasks"
assert "Plain text" in render("Due Date Description\n\x1b[38mPlain text\x1b[0m")
print("Task colors, background-code handling, column order, and literal descriptions passed")
