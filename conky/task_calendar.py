"""Render six months of Taskwarrior due dates as Conky text."""

import calendar
from datetime import datetime, timezone
import json
import subprocess

from theme import palette


def render(today, due_dates):
    theme = palette()
    colors, font = theme["colors"], theme["fonts"]["ui"]
    cal = calendar.Calendar(firstweekday=6)
    months = []
    for offset in range(6):
        year, month = divmod(today.year * 12 + today.month - 1 + offset, 12)
        month += 1
        heading_color = colors["primary"] if offset == 0 else colors["text"]
        lines = [f"${{font {font}:bold:size=8}}"
                 + f"${{color {heading_color}}}"
                 + f"{calendar.month_name[month]} {year}".center(20)
                 + f"${{font {font}:size=8}}${{color}}",
                 f"${{color {colors['muted']}}}Su Mo Tu We Th Fr Sa${{color}}"]
        for week in cal.monthdatescalendar(year, month):
            cells = []
            for day in week:
                if day.month != month:
                    cells.append("  ")
                    continue
                color = None
                if day in due_dates:
                    color = colors["warning"] if day == today else colors["error"] if day < today else colors["secondary"]
                elif day == today:
                    color = colors["primary"]
                cell = f"{day.day:2}"
                cells.append(f"${{color {color}}}{cell}${{color}}" if color else cell)
            lines.append(" ".join(cells))
        lines.extend([" " * 20] * (8 - len(lines)))
        months.append(lines)
    rows = ["\n".join(left + "    " + right for left, right in zip(months[i], months[i + 1]))
            for i in range(0, 6, 2)]
    return "\n".join(rows) + (
        f"\n${{voffset 8}}${{color {colors['primary']}}}Today${{color}}  ${{color {colors['secondary']}}}Due${{color}}  "
        f"${{color {colors['warning']}}}Due today${{color}}  ${{color {colors['error']}}}Overdue${{color}}"
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
