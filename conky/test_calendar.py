"""Run with: python3 conky/test_calendar.py."""

from datetime import date
import runpy
from pathlib import Path

render = runpy.run_path(str(Path(__file__).with_name("task_calendar.py")))["render"]
output = render(date(2026, 12, 15), {date(2026, 12, 14), date(2026, 12, 15), date(2027, 1, 2)})
rows = output.split("\n\n")
assert "December 2026" in rows[0] and "January 2027" in rows[0]
assert "February 2027" in rows[1] and "March 2027" in rows[1]
assert "April 2027" in rows[2] and "May 2027" in rows[2]
assert "${color #D33682}14${color}" in output
assert "${color #DC322F}15${color}" in output
assert "${color #CB4B16} 2${color}" in output
assert "${color #268BD2}29${color}" in render(date(2028, 2, 29), set())
print("Calendar checks passed")
