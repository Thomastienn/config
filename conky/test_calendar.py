"""Run with: python3 conky/test_calendar.py."""

from datetime import date
import runpy
from pathlib import Path
import re

render = runpy.run_path(str(Path(__file__).with_name("task_calendar.py")))["render"]
output = render(date(2026, 12, 15), {date(2026, 12, 14), date(2026, 12, 15), date(2027, 1, 2)})
lines = output.splitlines()
rows = ["\n".join(lines[i:i + 8]) for i in range(0, 24, 8)]
assert "December 2026" in rows[0] and "January 2027" in rows[0]
assert "February 2027" in rows[1] and "March 2027" in rows[1]
assert "April 2027" in rows[2] and "May 2027" in rows[2]
assert "${color #DBA0AA}14${color}" in output
assert "${color #DEC28A}15${color}" in output
assert "${color #C0AFD5} 2${color}" in output
assert "${color #A7CCAE}29${color}" in render(date(2028, 2, 29), set())
# Styling must not disturb the two fixed-width month columns.
plain = re.sub(r"\$\{(?:color|font)[^}]*\}", "", output)
assert all(len(line) == 44 for line in plain.splitlines()[:24])
assert "${color #A7CCAE}" in output.splitlines()[0]
print("Calendar checks passed")
