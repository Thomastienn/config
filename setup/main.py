#!/usr/bin/env python3
"""Repeatable Mint/Ubuntu setup. Git owns config; this applies its installation steps."""

import argparse
import configparser
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import tools
import power
import graphics
import codex
import hermes

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HOME = Path.home()
STATE = HOME / ".local/state/thomas-config"
CACHE = HOME / ".cache/thomas-config"
BACKUP = STATE / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")

sys.path.insert(0, str(REPO / "scripts"))
import theme


def run(args, **kwargs):
    print("+", shlex.join(str(arg) for arg in args), flush=True)
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def output(args):
    return subprocess.check_output([str(arg) for arg in args], text=True, stderr=subprocess.DEVNULL, timeout=30).strip()


def lines(name):
    return [line.split("#", 1)[0].strip() for line in (ROOT / name).read_text().splitlines()
            if line.split("#", 1)[0].strip()]


def backup(path):
    saved = BACKUP / path.relative_to(HOME)
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(saved))
    print(f"Backup: {path} -> {saved}")


def link(source, target, apply=True):
    if target.resolve() == source.resolve():
        return []
    if source.is_dir() and target.is_dir() and not target.is_symlink():
        return [item for child in sorted(source.iterdir()) if child.name != "__pycache__"
                for item in link(child, target / child.name, apply)]
    changes = [str(target.relative_to(HOME))]
    if apply:
        # Never traverse a foreign symlinked parent and alter another application's tree.
        for parent in reversed(target.parents):
            if parent == HOME or not parent.is_relative_to(HOME):
                continue
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                backup(parent)
            if not parent.exists():
                parent.mkdir()
        if target.exists() or target.is_symlink():
            backup(target)
        target.symlink_to(source, target_is_directory=source.is_dir())
    return changes


def configured_links():
    yield REPO, HOME / "thomas_config"
    for source, target in json.loads((ROOT / "links.json").read_text()).items():
        yield REPO / source, HOME / target
    # Keep this a real directory: systemctl writes enablement links below it.
    for source in sorted((REPO / "systemd/user").iterdir()):
        if source.suffix in (".service", ".timer"):
            yield source, HOME / ".config/systemd/user" / source.name
    # Fresh setup can link nvim to its source checkout; never replace that parent.
    nvim = (HOME / ".config/nvim").resolve()
    loader = nvim / "lua/lazy_setup.lua"
    if (nvim.is_relative_to(HOME) and loader.is_file() and 'import = "plugins"' in loader.read_text()
            and 'AstroNvim/AstroNvim' in loader.read_text() and (nvim / "lua/plugins").is_dir()
            and not any((nvim / p).is_symlink() for p in ["lua", "lua/plugins"])):
        yield REPO / "themes/nvim.lua", nvim / "lua/plugins/zz-desktop-theme.lua"


def firefox_links():
    for root in [HOME / ".mozilla/firefox", HOME / "snap/firefox/common/.mozilla/firefox"]:
        parser = configparser.ConfigParser()
        parser.read(root / "profiles.ini")
        defaults = [parser[s].get("Default") for s in parser.sections() if s.startswith("Install")]
        installs = configparser.ConfigParser()
        installs.read(root / "installs.ini")
        defaults += [installs[s]["Default"] for s in installs.sections() if "Default" in installs[s]]
        profiles = [parser[s] for s in parser.sections() if s.startswith("Profile")]
        for profile in profiles:
            selected = profile.get("Path") in defaults if defaults else profile.get("Default") == "1"
            if not selected:
                continue
            path = Path(profile["Path"])
            directory = root / path if profile.get("IsRelative", "1") == "1" else path
            if directory.is_dir():
                yield REPO / "firefox/user.js", directory / "user.js"
                for name in ["userChrome.css", "userContent.css"]:
                    yield REPO / "firefox" / name, directory / "chrome" / name


def apply_links():
    theme.apply(live=False)
    theme.bridge()
    changes = []
    for source, target in [*configured_links(), *firefox_links()]:
        changes.extend(link(source, target))
    for directory in [HOME / ".config/thomas-pdfs", HOME / ".cache/thomas-pdf-search"]:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    print(f"Applied {len(changes)} links. Existing conflicts backed up under {BACKUP}.")
    codex.configuration(HOME, backup)
    hermes.configuration(HOME, backup)
    if not any(target.name == "zz-desktop-theme.lua" for _, target in configured_links()):
        print("Pending: Neovim theme bridge needs the managed AstroNvim configuration.")


def settings(capture=False):
    # Homebrew's GSettings can use a different backend from the actual desktop.
    path = ROOT / "desktop/settings.json"
    data = json.loads(path.read_text())
    appearance = theme.gsettings(theme.load()[0])
    captured = {}
    for schema, values in appearance.items():
        data["gsettings"].setdefault(schema, {}).update(values)
    try:
        schemas = output(["/usr/bin/gsettings", "list-schemas"]).splitlines()
    except (OSError, subprocess.SubprocessError):
        print("Pending: desktop settings need gsettings and a user session.")
        return
    for schema, values in data["gsettings"].items():
        if schema not in schemas:
            continue
        for key, value in values.items():
            if capture:
                values[key] = output(["/usr/bin/gsettings", "get", schema, key])
                if key in appearance.get(schema, {}):
                    captured.setdefault(schema, {})[key] = values[key]
            else:
                run(["/usr/bin/gsettings", "set", schema, key, value])
    if capture:
        theme.capture_settings(captured, codex.toml_text)
        for schema, values in appearance.items():
            for key in values:
                data["gsettings"][schema].pop(key, None)
        # Only keys already in the allowlist; never clipboard data or tab contents.
        for key in data["copyq"]:
            try:
                value = output(["copyq", "config", key])
                if value:
                    data["copyq"][key] = value
            except (OSError, subprocess.SubprocessError):
                print(f"Could not capture CopyQ {key}; kept recorded value.")
        path.write_text(json.dumps(data, indent=2) + "\n")
    else:
        # CopyQ's CLI starts a server if needed; never start one during a headless install.
        if not os.environ.get("DISPLAY"):
            print("Pending: run setup.sh apply --configs-only in the desktop to configure CopyQ.")
            return
        for key, value in data["copyq"].items():
            try:
                run(["copyq", "config", key, value])
            except (OSError, subprocess.SubprocessError):
                print("Pending: open CopyQ, then rerun setup.sh apply --configs-only for its settings.")
                break


def services():
    if not (Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "bus").exists():
        print("Pending: log in, then run setup.sh apply --configs-only for user services.")
        return
    if (HOME / ".local/bin/dunst").exists():
        path = HOME / ".local/share/dbus-1/services/org.freedesktop.Notifications.service"
        text = ("[D-BUS Service]\nName=org.freedesktop.Notifications\n"
                f"Exec={HOME}/.local/bin/dunst\nSystemdService=dunst.service\n")
        if not path.exists() or path.read_text() != text:
            if path.exists() or path.is_symlink():
                backup(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    run(["systemctl", "--user", "daemon-reload"])
    environment = [key for key in ["DISPLAY", "XAUTHORITY"] if os.environ.get(key)]
    if environment:
        run(["systemctl", "--user", "import-environment", *environment])
    if os.environ.get("DISPLAY") and power.FILES[0][1].is_file():
        run(["systemctl", "--user", "start", "thomas-battery-mode.service"])
    if shutil.which("recollq") and shutil.which("recollindex"):
        run(["systemctl", "--user", "enable", "thomas-pdf-index.timer"])
        if not (Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) /
                "thomas-battery-mode/active").exists():
            run(["systemctl", "--user", "start", "thomas-pdf-index.timer"])
            run(["systemctl", "--user", "start", "--no-block", "thomas-pdf-index.service"])


def packages(extras):
    os_release = Path("/etc/os-release").read_text()
    if not re.search(r'^ID=(?:"?)(?:linuxmint|ubuntu)(?:"?)$', os_release, re.M):
        raise RuntimeError("Full installation supports Linux Mint and Ubuntu. Use link/check elsewhere.")
    run(["sudo", "apt-get", "update"])
    names = lines("apt.txt") + (lines("apt-extra.txt") if extras else [])
    if re.search(r'^ID="?linuxmint"?$', os_release, re.M):
        names += ["mint-themes", "mint-y-icons", "mint-cursor-themes", "firefox", "touchegg"]
    else:
        names += ["firefox"]
    run(["sudo", "apt-get", "install", "-y", "--no-install-recommends", *names])
    brew = Path("/home/linuxbrew/.linuxbrew/bin/brew")
    if not brew.exists():
        installer = CACHE / "homebrew-install.sh"
        run(["curl", "-fL", "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh", "-o", installer])
        run(["bash", installer])
    run([brew, "bundle", "install", "--no-upgrade", f"--file={REPO / 'Brewfile'}"])
    # The desktop's Brave shortcut needs its official repository on a fresh host.
    if not shutil.which("brave-browser"):
        key = CACHE / "brave-browser-archive-keyring.gpg"
        source = CACHE / "brave-browser-release.sources"
        run(["curl", "-fL", "https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg", "-o", key])
        run(["curl", "-fL", "https://brave-browser-apt-release.s3.brave.com/brave-browser.sources", "-o", source])
        run(["sudo", "install", "-m", "644", key, "/usr/share/keyrings/brave-browser-archive-keyring.gpg"])
        run(["sudo", "install", "-m", "644", source, "/etc/apt/sources.list.d/brave-browser-release.sources"])
        run(["sudo", "apt-get", "update"])
        run(["sudo", "apt-get", "install", "-y", "brave-browser"])
    run(["flatpak", "remote-add", "--user", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"])
    installed = output(["flatpak", "list", "--app", "--columns=application"]).splitlines()
    missing = [app for app in lines("flatpaks.txt") if app not in installed]
    if missing:
        run(["flatpak", "install", "--user", "-y", "flathub", *missing])


def check():
    gaps = power.check() + codex.configuration(HOME) + hermes.configuration(HOME)
    gaps += theme.check() + theme.bridge(check=True)
    for source, target in [*configured_links(), *firefox_links()]:
        gaps.extend("link: " + path for path in link(source, target, apply=False))
    for command in ["i3", "picom", "eww", "dunst", "dunstctl", "kitty", "tmux", "task", "zoxide",
                    "copyq", "tesseract", "xidlehook", "xidlehook-client", "betterlockscreen", "recollq", "brave-browser"]:
        if not shutil.which(command):
            gaps.append("command: " + command)
    for command, revision in [("picom", "v12.5"), ("dunst", "1.13"), ("eww", "fddb4a09")]:
        try:
            if revision not in output([command, "--version"]):
                gaps.append(f"version: {command} differs from recorded desktop build")
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        installed = output(["dpkg-query", "-W", "-f=${binary:Package}\t${db:Status-Status}\n"])
        names = {row.split("\t")[0].split(":")[0] for row in installed.splitlines() if row.endswith("\tinstalled")}
        gaps.extend("apt: " + name for name in lines("apt.txt") if name not in names)
        installed_apps = output(["flatpak", "list", "--app", "--columns=application"]).splitlines()
        gaps.extend("flatpak: " + app for app in lines("flatpaks.txt") if app not in installed_apps)
    except (OSError, subprocess.SubprocessError):
        gaps.append("package inventory unavailable")
    try:
        formulas = json.loads(output(["brew", "info", "--json=v2", "--installed"]))["formulae"]
        installed = {name for formula in formulas
                     for name in [formula["name"], formula["full_name"], *formula.get("aliases", []), *formula.get("oldnames", [])]}
        desired = re.findall(r'^brew "([^"]+)"', (REPO / "Brewfile").read_text(), re.M)
        gaps.extend("brew: " + name for name in desired if name not in installed)
    except (OSError, subprocess.SubprocessError):
        gaps.append("Homebrew inventory unavailable")
    if not list(firefox_links()):
        gaps.append("Firefox: create a default profile, then rerun setup.sh apply --configs-only")
    try:
        if "ComicShannsMono" not in output(["fc-match", "-f", "%{family}", "ComicShannsMono Nerd Font"]):
            gaps.append("font: ComicShannsMono Nerd Font")
    except (OSError, subprocess.SubprocessError):
        gaps.append("font inventory unavailable")
    try:
        if output(["systemctl", "--user", "is-enabled", "thomas-pdf-index.timer"]) != "enabled":
            gaps.append("service: PDF index timer not enabled")
    except (OSError, subprocess.SubprocessError):
        gaps.append("service: PDF index timer not enabled or user session unavailable")
    data = json.loads((ROOT / "desktop/settings.json").read_text())
    for schema, values in theme.gsettings(theme.load()[0]).items():
        data["gsettings"].setdefault(schema, {}).update(values)
    try:
        schemas = output(["/usr/bin/gsettings", "list-schemas"]).splitlines()
        for schema, values in data["gsettings"].items():
            if schema in schemas:
                gaps.extend(f"setting: {schema} {key}" for key, value in values.items()
                            if output(["/usr/bin/gsettings", "get", schema, key]) != value)
        if os.environ.get("DISPLAY"):
            for key, value in data["copyq"].items():
                actual = output(["copyq", "config", key])
                if not actual or actual != value:
                    gaps.append("CopyQ setting unavailable or different: " + key)
    except (OSError, subprocess.SubprocessError):
        gaps.append("desktop settings unavailable; check again inside the desktop session")
    for item in gaps:
        print("Pending:", item)
    print(f"{len(gaps)} setup differences. See README.md for manual browser/hardware steps.")
    return bool(gaps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="plan", choices=["plan", "apply", "link", "check", "capture"])
    parser.add_argument("--configs-only", action="store_true", help="skip packages, source builds and fonts")
    parser.add_argument("--extras", action="store_true", help="also install development tools, Codex skills/plugins, Hermes/Ollama and virtualization")
    parser.add_argument("--graphics", choices=["on-demand", "nvidia"],
                        help="explicitly select a PRIME profile during apply; activate at the next login")
    args = parser.parse_args()
    if args.graphics and args.command != "apply":
        parser.error("--graphics requires apply")
    if args.command == "plan":
        print("Target: Mint 22 / Ubuntu 24.04+, i3 on X11. Run as your normal user.")
        print("apply: APT + Brewfile + Flatpak apps, pinned desktop builds/fonts, links, desktop settings, user services.")
        print("apply --configs-only: links, desktop settings and services after a Git pull.")
        print("apply --extras: also restore development tools, Codex skills/plugins, Hermes/Ollama and virtualization.")
        print("link: only files/symlinks, no installations or session changes. Conflicts are backed up.")
        print("check: read-only differences. capture: refresh only allowlisted desktop settings.")
        print("No desktop restart. Browser sign-in/theme installation and hardware drivers remain manual.")
        return 0
    if args.command == "check":
        return check()
    if os.geteuid() == 0:
        raise RuntimeError("Run setup as your normal desktop user; it invokes sudo only for system packages.")
    if args.command == "capture":
        settings(capture=True)
        print("Captured allowlisted desktop preferences. Review git diff before committing.")
        return 0
    if not args.configs_only and args.command == "apply":
        CACHE.mkdir(parents=True, exist_ok=True)
        # Make freshly installed tools available to build steps without sourcing interactive bashrc.
        os.environ["PATH"] = f"{HOME}/.local/bin:{HOME}/.cargo/bin:/home/linuxbrew/.linuxbrew/bin:" + os.environ["PATH"]
        packages(args.extras)
        if args.extras:
            python = HOME / ".virtualenvs/neovim/bin/python"
            if not python.exists():
                run(["/usr/bin/python3", "-m", "venv", python.parents[1]])
            run([python, "-m", "pip", "install", "-r", ROOT / "neovim-requirements.txt"])
            run(["npm", "install", "-g", *lines("npm-extra.txt")])
            run(["cargo", "install", "--locked", "code-minimap", "--version", "0.6.8"])
            run(["sudo", "systemctl", "enable", "--now", "libvirtd"])
            run(["sudo", "usermod", "-aG", "libvirt", os.environ["USER"]])
        tools.install(HOME, CACHE, link)
        tools.assets(HOME, CACHE)
        if args.extras:
            hermes.install(HOME, CACHE, run)
    refresh_theme = bool(theme.check() + theme.bridge(check=True)) or theme.needs_activation()
    if args.command == "apply":
        theme.assets(theme.load()[0])
    apply_links()
    if args.command == "apply":
        if args.extras and not args.configs_only:
            codex.install(HOME, run)
        power.install(run)
        if args.graphics:
            graphics.configure(args.graphics, run)
        settings()
        services()
        if refresh_theme:
            theme.reload_desktop(theme.load()[0])
    print("Setup applied. See README.md for activation and manual steps; desktop was not restarted.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        sys.exit(1)
