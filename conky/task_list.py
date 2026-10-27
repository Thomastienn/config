"""Show Taskwarrior's date-only report with its terminal colors in Conky."""

import re
import subprocess

from theme import palette


COMMAND = [
    "/home/linuxbrew/.linuxbrew/bin/task", "rc.verbose=label",
    "rc.color=on", "rc._forcecolor=on", "rc.detection=off", "rc.defaultwidth=48",
    "rc.report.next.columns=due.relative,due,description.truncated",
    "rc.report.next.labels=Due,Date,Description", "rc.report.next.dateformat=Y-M-D",
    "rc.column.padding=1", "limit:12", "next",
]
SGR = re.compile(r"\x1b\[([0-9;]*)m")
# Keep extended foreground/background parameters together when reading SGR codes.
OPERATIONS = re.compile(r"(?:38|48);(?:5;\d+|2;\d+;\d+;\d+)|\d+")
ANSI_COLORS = {n: color[1:].upper() for n, color in enumerate(palette()["terminal"]["ansi"])}


def indexed_color(n):
    if n < 16:
        return ANSI_COLORS[n]
    if n < 232:
        levels = (0, 95, 135, 175, 215, 255)
        n -= 16
        rgb = (levels[n // 36], levels[n // 6 % 6], levels[n % 6])
    else:
        rgb = (8 + 10 * (n - 232),) * 3
    return "".join(f"{value:02X}" for value in rgb)


def color_codes(match):
    output = []
    for operation in OPERATIONS.findall(match[1] or "0"):
        codes = [int(n) for n in operation.split(";")]
        color = None
        if codes[0] in (0, 39):
            output.append("${color}")
        elif 30 <= codes[0] <= 37:
            color = indexed_color(codes[0] - 30)
        elif 90 <= codes[0] <= 97:
            color = indexed_color(codes[0] - 90 + 8)
        elif len(codes) == 3 and codes[:2] == [38, 5] and 0 <= codes[2] <= 255:
            color = indexed_color(codes[2])
        elif len(codes) == 5 and codes[:2] == [38, 2] and all(0 <= n <= 255 for n in codes[2:]):
            color = "".join(f"{n:02X}" for n in codes[2:])
        if color:
            output.append(f"${{color #{color}}}")
    return "".join(output)


def render(report):
    theme = palette()
    colors, font = theme["colors"], theme["fonts"]["ui"]
    # Task descriptions must stay literal when execp parses the generated colors.
    lines = SGR.sub(color_codes, report.replace("$", "$$")).strip("\n").splitlines()
    if not lines:
        return "No pending tasks"
    return (f"${{color {colors['muted']}}}${{font {font}:size=9}}" + lines[0]
            + f"${{color}}\n${{color {colors['separator']}}}${{hr 1}}${{color}}\n"
            + "\n".join(lines[1:]) + "${color}")


def main():
    try:
        result = subprocess.run(COMMAND, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        print("Taskwarrior unavailable")
        return
    print(render(result.stdout) if result.returncode in (0, 1) else "Taskwarrior unavailable")


if __name__ == "__main__":
    main()
