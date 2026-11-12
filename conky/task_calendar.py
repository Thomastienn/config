"""Pass Taskwarrior due dates to the Conky calendar that calendar.lua draws."""

from datetime import datetime, timezone
import json
import subprocess


def render(due_dates):
    # Only digits enter Conky's parsed output; task text never becomes commands.
    return "${lua calendar " + " ".join(sorted(f"{day:%Y%m%d}" for day in due_dates)) + "}"


def main():
    result = subprocess.run(
        ["/home/linuxbrew/.linuxbrew/bin/task", "rc.verbose=nothing",
         "status:pending", "-nocal", "export"],
        capture_output=True, text=True, check=True,
    )
    due_dates = {
        datetime.strptime(task["due"], "%Y%m%dT%H%M%SZ")
        .replace(tzinfo=timezone.utc).astimezone().date()
        for task in json.loads(result.stdout) if task.get("due")
    }
    print(render(due_dates))


if __name__ == "__main__":
    main()
