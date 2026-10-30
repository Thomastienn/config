#!/usr/bin/python3
"""Render and apply the repository's selected desktop theme without restarting apps."""

import argparse
import ast
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib


REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "themes"
SELECTOR = THEMES / "active"
COLOR_KEYS = {
    "background", "surface", "text", "muted", "primary", "secondary", "warning", "error",
    "border", "separator", "selection", "urgent_background", "pane_border", "gradient_start",
    "gradient_end", "menu_text", "panel_separator", "shade1", "shade3", "shade4", "shade5",
    "shade6", "shade7",
}
FONT_KEYS = {"ui", "proportional", "terminal", "terminal_size", "gtk2", "gtk3", "lock", "lock_clock"}
DESKTOP_KEYS = {"gtk2", "gtk3", "gtk2_icons", "icons", "cursor", "cursor_size", "wm"}
TOKEN = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")


def state():
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "thomas-config/theme"


def load(file=None):
    if file is None:
        file = SELECTOR.read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.toml", file):
            raise ValueError("themes/active must contain one preset filename, for example cozy-mint.toml")
        path = THEMES / file
    else:
        path = Path(file)
        if not path.is_absolute():
            path = path if path.is_file() else THEMES / path
    path = path.resolve()
    if path.parent != THEMES.resolve() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.toml", path.name):
        raise ValueError("Keep presets directly under the repository's themes/ directory for portable selection")
    data = tomllib.loads(path.read_text())
    validate(data)
    return data, path


def validate(data):
    expected = {"name", "mode", "wallpaper", "colors", "fonts", "desktop", "terminal"}
    if set(data) != expected or data["mode"] not in ("dark", "light"):
        raise ValueError("Preset needs name, mode (dark/light), wallpaper, colors, fonts, desktop, terminal")
    for section, keys in [("colors", COLOR_KEYS), ("fonts", FONT_KEYS), ("desktop", DESKTOP_KEYS),
                          ("terminal", {"ansi", "bat", "taskwarrior"})]:
        if not isinstance(data[section], dict):
            raise ValueError(f"{section} must be a table")
        if set(data[section]) != keys:
            raise ValueError(f"{section}: missing {keys - set(data[section])}, unknown {set(data[section]) - keys}")
    ansi = data["terminal"]["ansi"]
    if not isinstance(ansi, list) or len(ansi) != 16:
        raise ValueError("terminal.ansi must contain exactly 16 colors")
    for color in [*data["colors"].values(), *ansi]:
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(f"Expected #RRGGBB color, got {color!r}")
    strings = [data["name"], *[v for k, v in data["fonts"].items() if k != "terminal_size"],
               *[v for k, v in data["desktop"].items() if k != "cursor_size"],
               data["terminal"]["bat"], data["terminal"]["taskwarrior"]]
    for value in strings:
        if not isinstance(value, str) or not re.fullmatch(r"[\w][\w .,+:-]*", value) or len(value) > 120:
            raise ValueError(f"Invalid font, theme name or label: {value!r}")
    size = data["fonts"]["terminal_size"]
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or not 4 <= size <= 72:
        raise ValueError("fonts.terminal_size must be between 4 and 72")
    size = data["desktop"]["cursor_size"]
    if type(size) is not int or not 0 <= size <= 128:
        raise ValueError("desktop.cursor_size must be an integer between 0 and 128")
    wallpaper = data["wallpaper"]
    if (not isinstance(wallpaper, str) or not re.fullmatch(r"[\w./ -]+", wallpaper)
            or Path(wallpaper).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
            or Path(wallpaper).is_absolute() or not (REPO / wallpaper).resolve().is_relative_to(REPO)
            or not (REPO / wallpaper).is_file()):
        raise ValueError("wallpaper must name an existing image inside this repository")


def gsettings(data):
    desktop, fonts = data["desktop"], data["fonts"]
    shared = {"gtk-theme": repr(desktop["gtk3"]), "icon-theme": repr(desktop["icons"]),
              "cursor-theme": repr(desktop["cursor"]), "font-name": repr(fonts["gtk3"])}
    return {
        "org.cinnamon.desktop.interface": dict(shared),
        "org.cinnamon.desktop.wm.preferences": {"theme": repr(desktop["wm"]), "titlebar-font": repr(fonts["gtk3"])},
        "org.gnome.desktop.interface": {**shared, "monospace-font-name": repr(fonts["gtk3"]),
                                        "color-scheme": repr("prefer-" + data["mode"])},
    }


def capture_settings(values, serialize):
    data, path = load()
    interface = values.get("org.gnome.desktop.interface") or values.get("org.cinnamon.desktop.interface", {})
    for key, target in [("gtk-theme", "gtk3"), ("icon-theme", "icons"), ("cursor-theme", "cursor")]:
        if key in interface:
            data["desktop"][target] = ast.literal_eval(interface[key])
    if "font-name" in interface:
        data["fonts"]["gtk3"] = ast.literal_eval(interface["font-name"])
    if "color-scheme" in interface:
        data["mode"] = "light" if ast.literal_eval(interface["color-scheme"]) == "prefer-light" else "dark"
    wm = values.get("org.cinnamon.desktop.wm.preferences", {})
    if "theme" in wm:
        data["desktop"]["wm"] = ast.literal_eval(wm["theme"])
    validate(data)
    atomic(path, serialize(data).encode())


def render(data, preset):
    values = {"name": data["name"], "name_json": json.dumps(data["name"]), "mode": data["mode"],
              "wallpaper": str(REPO / data["wallpaper"]), "wallpaper_shell": shlex.quote(str(REPO / data["wallpaper"]))}
    icons = [Path.home() / ".local/share/icons" / data["desktop"]["icons"],
             Path.home() / ".icons" / data["desktop"]["icons"],
             Path("/usr/share/icons") / data["desktop"]["icons"]]
    for section in ["colors", "fonts", "desktop", "terminal"]:
        values.update({f"{section}.{key}": str(value) for key, value in data[section].items() if not isinstance(value, list)})
    for key, value in data["colors"].items():
        rgb = [int(value[n:n + 2], 16) for n in (1, 3, 5)]
        values.update({f"hex.{key}": value[1:], f"rgb.{key}": ", ".join(map(str, rgb)),
                       f"float.{key}": ", ".join(f"{n}.0" for n in rgb)})
    for index, color in enumerate(data["terminal"]["ansi"]):
        values[f"ansi.{index}"] = color
    result = {}
    digest = hashlib.sha256(preset.name.encode() + preset.read_bytes() + Path(__file__).read_bytes())
    for source in sorted((THEMES / "templates").rglob("*.in")):
        relative = str(source.relative_to(THEMES / "templates"))[:-3]
        content = source.read_text()
        digest.update(relative.encode() + content.encode())
        if relative == "dunst/dunstrc":
            # Local icon folders may contain only overrides; resolve each file independently.
            content = re.sub(r"\{\{icons_root\}\}/([\w./-]+)", lambda match: str(next(
                (root / match[1] for root in icons if (root / match[1]).is_file()), Path(match[1]).stem)), content)
        try:
            content = TOKEN.sub(lambda match: values[match[1]], content)
        except KeyError as error:
            raise ValueError(f"Unknown template token in {relative}: {error}") from error
        if "{{" in content:
            raise ValueError(f"Unexpanded theme token in {relative}")
        if relative.endswith(".json"):
            json.loads(content)
        result[relative] = content
    bridge = THEMES / "nvim.lua"
    if bridge.exists():
        digest.update(bridge.read_bytes())
    palette = {**data, "revision": digest.hexdigest(), "preset": preset.name}
    result["palette.json"] = json.dumps(palette, indent=2) + "\n"
    colors = data["colors"]
    lua = ["return {", "  colors = {"]
    for key, color in colors.items():
        lua.append(f'    {key} = {{{int(color[1:3], 16)}/255, {int(color[3:5], 16)}/255, {int(color[5:7], 16)}/255}},')
    lua += ["  },", "  fonts = { ui = " + json.dumps(data["fonts"]["ui"], ensure_ascii=False) + " },", "}"]
    result["palette.lua"] = "\n".join(lua) + "\n"
    exports = {"THEME_NAME": data["name"], "THEME_RESET": r"\033[00m", "THEME_BOLD": r"\033[1m"}
    for key, color in colors.items():
        exports["THEME_" + key.upper()] = color
    for key, role in {"THEME_COLOR1": "primary", "THEME_COLOR2": "text", "THEME_COLOR3": "secondary",
                      "THEME_COLOR4": "primary", "THEME_COLOR5": "error", "THEME_COLOR6": "secondary",
                      "THEME_GRAY": "muted"}.items():
        exports[key] = r"\033[38;2;" + ";".join(str(int(colors[role][i:i + 2], 16)) for i in (1, 3, 5)) + "m"
    for key, role in {"CONKY_COLOR1": "primary", "CONKY_COLOR2": "text", "CONKY_COLOR3": "muted",
                      "CONKY_COLOR4": "separator", "CONKY_GRAPH1": "primary", "CONKY_GRAPH2": "secondary"}.items():
        exports[key] = colors[role][1:]
    for key, role in {"PRIMARY": "primary", "ACCENT": "secondary", "SECONDARY": "surface",
                      "TERTIARY": "warning", "HIGHLIGHT": "primary"}.items():
        exports["TMUX_COLOR_" + key] = colors[role]
    exports["BAT_THEME"] = data["terminal"]["bat"]
    exports["FZF_DEFAULT_OPTS"] = (
        "--height=40% --layout=reverse --border=rounded --info=inline "
        f"--color=fg:{colors['text']},bg:-1,hl:{colors['primary']},fg+:{colors['text']},bg+:{colors['surface']},hl+:{colors['primary']} "
        f"--color=info:{colors['muted']},prompt:{colors['primary']},pointer:{colors['secondary']},marker:{colors['secondary']},"
        f"spinner:{colors['secondary']},header:{colors['muted']},border:{colors['separator']},gutter:-1")
    result["shell.sh"] = "# Generated by theme; edit the selected TOML preset instead.\n" + "".join(
        f"export {key}={shlex.quote(value)}\n" for key, value in exports.items())
    return result


def palette():
    try:
        return json.loads((state() / "generated/palette.json").read_text())
    except FileNotFoundError:
        return load()[0]


def atomic(path, content):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing to replace symlink: {path}")
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".theme-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def bridge(check=False):
    path = THEMES / ".generated"
    target = state() / "generated"
    if path.is_symlink() and path.resolve() == target.resolve():
        return []
    if not check:
        if path.exists() or path.is_symlink():
            saved = state() / "backups" / ("generated-link-" + __import__("time").strftime("%Y%m%d-%H%M%S"))
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path, saved)
            print(f"Backup: {path} -> {saved}")
        path.symlink_to(target, target_is_directory=True)
    return ["theme: generated configuration link"]


def assets(data):
    missing = []
    home = Path.home()
    for kind, names in [("themes", [data["desktop"][key] for key in ("gtk2", "gtk3", "wm")]),
                        ("icons", [data["desktop"][key] for key in ("gtk2_icons", "icons", "cursor")])]:
        roots = [home / ".local/share" / kind, home / (".themes" if kind == "themes" else ".icons"),
                 Path("/usr/share") / kind]
        for name in set(names):
            if not any((root / name).is_dir() for root in roots):
                missing.append(f"{kind}: {name}")
    for key in ("ui", "proportional", "terminal", "lock", "lock_clock"):
        font = data["fonts"][key]
        try:
            matched = subprocess.check_output(["fc-match", "-f", "%{family}", font], text=True, timeout=5)
            normal = lambda value: re.sub(r"[^a-z0-9]", "", value.lower()).removesuffix("light")
            if not any(normal(font) == normal(family) for family in matched.split(",")):
                missing.append(f"font: {font}")
        except (OSError, subprocess.SubprocessError):
            missing.append(f"font inventory unavailable: {font}")
    bat = shutil.which("bat") or shutil.which("batcat")
    if bat:
        try:
            skins = subprocess.check_output([bat, "--list-themes", "--color=never"], text=True, timeout=10).splitlines()
            if data["terminal"]["bat"] not in [skin.strip() for skin in skins]:
                missing.append(f"bat theme: {data['terminal']['bat']}")
        except (OSError, subprocess.SubprocessError):
            missing.append("bat theme inventory unavailable")
    task = shutil.which("task")
    roots = [Path(task).resolve().parents[1]] if task else []
    roots.append(Path("/usr"))
    skin = data["terminal"]["taskwarrior"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.theme", skin) or not any(
        (root / directory / skin).is_file() for root in roots
        for directory in ("share/doc/task/rc", "share/doc/taskwarrior/rc", "share/taskwarrior")):
        missing.append(f"Taskwarrior theme: {skin}")
    if missing:
        raise ValueError("Install selected assets through setup before switching: " + "; ".join(missing))


def apply(file=None, live=True):
    root = state()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (root / "switch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data, preset = load(file)
        outputs = render(data, preset)
        if live:
            assets(data)
        destination = root / "generated"
        for name in outputs:
            target = destination / name
            if target.is_symlink() or any(p.is_symlink() for p in [destination, *target.parents]
                                          if p == destination or p.is_relative_to(destination)):
                raise ValueError(f"Refusing symlinked generated path: {target}")
        if SELECTOR.is_symlink():
            raise ValueError("themes/active must be a regular file")
        old = {}
        changed_settings = []
        try:
            with tempfile.TemporaryDirectory(prefix="staging-", dir=root) as temporary:
                for name, text in outputs.items():
                    staged = Path(temporary) / name
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    staged.write_text(text)
                if shutil.which("i3"):
                    subprocess.run(["i3", "-C", "-c", str(Path(temporary) / "i3/config")], check=True,
                                   env=dict(os.environ, XDG_RUNTIME_DIR=temporary), capture_output=True, timeout=15)
                for name in outputs:
                    target = destination / name
                    previous = target.read_bytes() if target.exists() else None
                    atomic(target, (Path(temporary) / name).read_bytes())
                    old[target] = previous
            if live:
                changed_settings = apply_settings(data)
            if file is not None:
                old[SELECTOR] = SELECTOR.read_bytes()
                atomic(SELECTOR, (preset.name + "\n").encode())
        except Exception:
            for schema, key, value in reversed(changed_settings):
                subprocess.run(["/usr/bin/gsettings", "set", schema, key, value], check=False)
            for target, content in reversed(list(old.items())):
                if content is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic(target, content)
            raise
        print(f"Theme: {data['name']} ({preset.name})")
        if live:
            reload_desktop(data)
    return data


def apply_settings(data):
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        print("Pending: GTK desktop settings need a user session.")
        return []
    previous = []
    try:
        schemas = subprocess.check_output(["/usr/bin/gsettings", "list-schemas"], text=True).splitlines()
        for schema, values in gsettings(data).items():
            if schema not in schemas:
                continue
            for key, value in values.items():
                old = subprocess.check_output(["/usr/bin/gsettings", "get", schema, key], text=True).strip()
                if old != value:
                    subprocess.run(["/usr/bin/gsettings", "set", schema, key, value], check=True)
                    previous.append((schema, key, old))
    except Exception:
        for schema, key, value in reversed(previous):
            subprocess.run(["/usr/bin/gsettings", "set", schema, key, value], check=False)
        raise
    return previous


def check(file=None):
    data, preset = load(file)
    outputs = render(data, preset)
    differences = [f"theme: {name}" for name, text in outputs.items()
                   if not (state() / "generated" / name).is_file()
                   or (state() / "generated" / name).read_text() != text]
    return differences


def needs_activation():
    try:
        revision = json.loads((state() / "generated/palette.json").read_text())["revision"]
        return (state() / "activated.sha256").read_text() != revision
    except (FileNotFoundError, ValueError, KeyError):
        return True


def command(args, **kwargs):
    try:
        subprocess.run([str(arg) for arg in args], check=True, timeout=kwargs.pop("timeout", 15),
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kwargs)
        return True
    except (OSError, subprocess.SubprocessError) as error:
        detail = getattr(error, "stderr", b"") or str(error)
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace").strip()
        print(f"Pending: {args[0]}: {detail}")
        return False


def processes(name):
    found = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid == os.getuid() and (path / "comm").read_text().strip() == name:
                environment = (path / "environ").read_bytes().split(b"\0")
                if f"DISPLAY={os.environ.get('DISPLAY', '')}".encode() in environment:
                    found.append(int(path.name))
        except (OSError, ProcessLookupError):
            pass
    return found


def reload_desktop(data):
    if not os.environ.get("DISPLAY"):
        print("Pending: run theme apply inside the desktop session for live activation.")
        return
    success = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
    success = command(["feh", "--bg-scale", REPO / data["wallpaper"]]) and success
    cursor = data["desktop"]
    resources = f"Xcursor.theme: {cursor['cursor']}\nXcursor.size: {cursor['cursor_size']}\n"
    success = command(["xrdb", "-merge"], input=resources.encode()) and success
    environment = dict(os.environ, XCURSOR_THEME=cursor["cursor"], XCURSOR_SIZE=str(cursor["cursor_size"]))
    success = command(["xsetroot", "-cursor_name", "left_ptr"], env=environment) and success
    if processes("i3"):
        success = command(["i3-msg", "reload"]) and success
    for name in ("kitty", "picom"):
        for pid in processes(name):
            try:
                if name == "picom" and str(REPO / "picom").encode() not in Path(f"/proc/{pid}/cmdline").read_bytes():
                    continue
                os.kill(pid, signal.SIGUSR1)
            except OSError as error:
                success = False
                print(f"Pending: {name} reload: {error}")
    if processes("polybar"):
        success = command(["polybar-msg", "cmd", "restart"]) and success
    if processes("dunst"):
        success = command(["/usr/bin/python3", REPO / "scripts/desktop-controls.py", "reload-dnd"]) and success
    if processes("eww"):
        success = command(["eww", "-c", REPO / "eww", "reload"]) and success
    if shutil.which("tmux") and subprocess.run(["tmux", "has-session"], capture_output=True).returncode == 0:
        success = command(["tmux", "source-file", Path.home() / ".tmux.conf"]) and success
    if processes("conky"):
        try:
            spec = importlib.util.spec_from_file_location("battery_mode", REPO / "scripts/battery-mode.py")
            battery = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(battery)
            def panels():
                nonlocal success
                names = sorted({name for name, _ in battery.conky_processes().values()})
                if names and not battery.ACTIVE.exists():
                    success = command([REPO / "conky/run.sh", *names], start_new_session=True) and success
            battery.locked(panels)
        except (OSError, ImportError, subprocess.SubprocessError) as error:
            success = False
            print(f"Pending: Conky refresh: {error}")
    fingerprint = hashlib.sha256((REPO / data["wallpaper"]).read_bytes()).hexdigest()
    marker = state() / "lock-wallpaper.sha256"
    if not marker.is_file() or marker.read_text() != fingerprint:
        if command(["betterlockscreen", "-u", REPO / data["wallpaper"]], timeout=180):
            atomic(marker, fingerprint.encode())
        else:
            success = False
    if success:
        try:
            revision = json.loads((state() / "generated/palette.json").read_text())["revision"]
            atomic(state() / "activated.sha256", revision.encode())
        except OSError as error:
            print(f"Pending: activation marker: {error}")
    print("Pending: reopen existing shells for prompt/ble.sh/FZF; relaunch TUIs such as Codex if they cache old colors.")
    print("Pending: restart Firefox when convenient; reload the Brave theme at brave://extensions.")
    print("Neovim: focus the editor or run :DesktopThemeReload (restart once after first setup).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply", "check", "shell"])
    parser.add_argument("file", nargs="?", help="preset under this repository's themes/ directory")
    args = parser.parse_args()
    if args.action == "shell":
        data, preset = load(args.file)
        print(render(data, preset)["shell.sh"], end="")
    elif args.action == "check":
        data, _ = load(args.file)
        assets(data)
        differences = check(args.file) + bridge(check=True)
        for item in differences:
            print("Pending:", item)
        print(f"{len(differences)} theme differences.")
        return bool(differences)
    else:
        if bridge(check=True):
            raise ValueError("Run ./setup.sh link once to connect generated desktop configuration")
        apply(args.file)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Theme error: {error}", file=sys.stderr)
        sys.exit(1)
