"""Render six months of Taskwarrior due dates as Conky text."""

import calendar
from datetime import datetime, timezone
import json
import subprocess


def render(today, due_dates):
    cal = calendar.Calendar(firstweekday=6)
    months = []
    for offset in range(6):
        year, month = divmod(today.year * 12 + today.month - 1 + offset, 12)
        month += 1
        lines = [f"{calendar.month_name[month]} {year}".center(20),
                 "Su Mo Tu We Th Fr Sa"]
        for week in cal.monthdatescalendar(year, month):
            cells = []
            for day in week:
                if day.month != month:
                    cells.append("  ")
                    continue
                color = None
                if day in due_dates:
                    color = "DC322F" if day == today else "D33682" if day < today else "CB4B16"
                elif day == today:
                    color = "268BD2"
                cell = f"{day.day:2}"
                cells.append(f"${{color #{color}}}{cell}${{color}}" if color else cell)
            lines.append(" ".join(cells))
        lines.extend([" " * 20] * (8 - len(lines)))
        months.append(lines)
    rows = ["\n".join(left + "    " + right for left, right in zip(months[i], months[i + 1]))
            for i in range(0, 6, 2)]
    return "\n\n".join(rows) + (
        "\n\n${color #268BD2}Today${color}  ${color #CB4B16}Due${color}  "
        "${color #DC322F}Due today${color}  ${color #D33682}Overdue${color}"
    )


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
    print(render(datetime.now().astimezone().date(), due_dates))


if __name__ == "__main__":
    main()
