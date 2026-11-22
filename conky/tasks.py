"""Taskwarrior for the Conky cards.

No argument, for calendar.lua: due days on the first line, then the most urgent pending tasks.
`done`, for momentum.lua: how many tasks were completed on each of the last DAYS days, oldest first.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys


# Rows and description characters that fit the task column calendar.lua draws.
LIMIT, WIDTH = 12, 23
# The 31 week columns momentum.lua draws.
DAYS = 31 * 7


def local(stamp):
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone()


def label(day, today):
    days = (day - today).days
    if days == 0:
        return "today"
    # Day padded so the days line up in a column in the monospace theme font.
    return f"{days}d {day.day:>2} {day:%b}"


def render(tasks, now):
    # Tasks tagged nocal stay off the calendar; waiting tasks stay off the list, as in the next report.
    lines = [" ".join(sorted({f"{local(task['due']):%Y%m%d}" for task in tasks
                              if task.get("due") and "nocal" not in task.get("tags", [])}))]
    listed = [task for task in tasks if not (task.get("wait") and local(task["wait"]) > now)]
    for task in sorted(listed, key=lambda task: -task.get("urgency", 0))[:LIMIT]:
        # Tabs and newlines separate fields, so they never survive inside a description.
        text = " ".join(task["description"].split())
        if len(text) > WIDTH:
            text = text[:WIDTH - 1] + "…"
        if task.get("due"):
            day = local(task["due"]).date()
            lines.append(f"{day:%Y%m%d}\t{label(day, now.date())}\t{text}")
        else:
            lines.append(f"-\t\t{text}")
    return "\n".join(lines)


def done(tasks, today):
    counts = Counter(local(task["end"]).date() for task in tasks if task.get("end"))
    return " ".join(str(counts[today - timedelta(days=back)]) for back in reversed(range(DAYS)))


def export(*filters):
    result = subprocess.run(
        ["/home/linuxbrew/.linuxbrew/bin/task", "rc.verbose=nothing", *filters, "export"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


def main():
    now = datetime.now().astimezone()
    if sys.argv[1:] == ["done"]:
        print(done(export("status:completed", f"end.after:today-{DAYS}d"), now.date()))
    else:
        print(render(export("status:pending"), now))


if __name__ == "__main__":
    main()
