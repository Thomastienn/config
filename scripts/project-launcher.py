#!/usr/bin/env python3
"""Open a remembered directory in a new normal tmux window."""

import html
from pathlib import Path
import subprocess

TMUX = "/home/linuxbrew/.linuxbrew/bin/tmux"
KITTY = str(Path.home() / ".local/kitty.app/bin/kitty")


def main():
    result = subprocess.run(["/home/linuxbrew/.linuxbrew/bin/zoxide", "query", "--list"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not read folder history.")
    paths = [Path(line) for line in result.stdout.splitlines() if Path(line).is_dir()]
    if not paths:
        raise RuntimeError("No remembered folders yet. Visit a folder in your terminal first.")
    home = Path.home()
    labels = [str(Path("~") / path.relative_to(home)) if path.is_relative_to(home)
              else str(path) for path in paths]
    choice = subprocess.run(
        ["rofi", "-dmenu", "-i", "-no-custom", "-format", "i",
         "-theme-str", 'entry { placeholder: "Open folder…"; }'],
        input="\n".join(labels), capture_output=True, text=True,
    )
    if choice.returncode != 0:
        return
    folder = paths[int(choice.stdout.strip())]
    if not folder.is_dir():
        raise RuntimeError(f"Folder no longer exists: {folder}")
    sessions = subprocess.run([TMUX, "list-sessions", "-F", "#{session_activity}\t#{session_id}"],
                              capture_output=True, text=True)
    if sessions.returncode == 0 and sessions.stdout.strip():
        session = max((int(line.split()[0]), line.split()[1])
                      for line in sessions.stdout.splitlines())[1]
        subprocess.run([TMUX, "new-window", "-t", session, "-c", str(folder)], check=True)
    else:
        created = subprocess.run([TMUX, "new-session", "-d", "-s", "main", "-c", str(folder),
                                  "-P", "-F", "#{session_id}"],
                                 capture_output=True, text=True, check=True)
        session = created.stdout.strip()
    subprocess.Popen([KITTY, TMUX, "attach-session", "-t", session], start_new_session=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
        subprocess.run(["notify-send", "-u", "critical", "Folder launcher failed",
                        html.escape(str(error))])
