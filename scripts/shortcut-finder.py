#!/usr/bin/env python3
"""Show keyboard shortcuts from the current i3 config without executing them."""

import html
from pathlib import Path
import re
import subprocess


def shortcuts(config):
    variables = {}
    mode = "default"
    label = ""
    rows = []
    config = re.sub(r"\\\s*\n", " ", config)

    def expand(text):
        return re.sub(r"\$[\w-]+", lambda match: variables.get(match[0], match[0]), text)

    for raw in config.splitlines():
        line = raw.strip()
        if line.startswith("# shortcut:"):
            label = line.partition(":")[2].strip()
            continue
        if not line or line.startswith("#"):
            continue
        if line.startswith("set "):
            _, name, value = line.split(None, 2)
            variables[name] = expand(value.strip('"'))
        elif line.startswith("mode ") and line.endswith("{"):
            mode = line.split('"')[1]
        elif line == "}":
            mode = "default"
        elif line.startswith("bindsym ") or line.startswith("bindcode "):
            parts = line.split()
            index = 1
            while parts[index].startswith("--"):
                index += 1
            keys = expand(parts[index])
            keys = "+".join({"Mod4": "Super", "Mod1": "Alt", "Return": "Enter",
                             "grave": "`", "space": "Space"}.get(key, key) for key in keys.split("+"))
            action = label or expand(" ".join(parts[index + 1:]))
            prefix = "" if mode == "default" else f"{mode.title()} mode: "
            rows.append(f"{prefix}{keys} — {action}")
        label = ""
    return rows


def main():
    config = (Path.home() / ".config/i3/config").read_text()
    rows = shortcuts(config)
    if not rows:
        raise RuntimeError("No shortcuts found in the i3 configuration.")
    choice = subprocess.run(
        ["rofi", "-dmenu", "-i", "-matching", "fuzzy", "-sort", "-no-custom", "-format", "i",
         "-theme-str", 'window { width: 780px; } entry { placeholder: "Find shortcut…"; }'],
        input="\n".join(rows), capture_output=True, text=True,
    )
    if choice.returncode == 1:
        return
    if choice.returncode != 0:
        raise RuntimeError(choice.stderr.strip() or "Could not open shortcut finder.")
    selected = rows[int(choice.stdout.strip())]
    subprocess.run(["notify-send", "Keyboard shortcut", html.escape(selected)], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Shortcut finder failed",
                        html.escape(str(error))])
