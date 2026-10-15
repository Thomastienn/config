"""Pinned desktop builds and appearance assets; called only by setup/main.py."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


ROOT = Path(__file__).resolve().parent


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def checkout(name, spec, cache):
    path = cache / "sources" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", spec["url"], path])
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    if dirty:
        raise RuntimeError(f"Build source has local changes; preserve them before rerunning: {path}")
    run(["git", "-C", path, "fetch", "--depth", "1", "origin", spec["rev"]])
    run(["git", "-C", path, "checkout", "--detach", spec["rev"]])
    if (path / ".gitmodules").exists():
        run(["git", "-C", path, "submodule", "update", "--init", "--recursive", "--depth", "1"])
    return path


def install(home, cache, link):
    prefix = home / ".local"
    binaries = prefix / "bin"
    binaries.mkdir(parents=True, exist_ok=True)
    specs = json.loads((ROOT / "sources.json").read_text())
    markers = cache / "installed"
    markers.mkdir(parents=True, exist_ok=True)
    outputs = {"picom": binaries / "picom", "dunst": binaries / "dunst", "eww": binaries / "eww",
               "blesh": prefix / "share/blesh/ble.sh", "i3lock-color": binaries / "i3lock",
               "betterlockscreen": binaries / "betterlockscreen"}
    for name, spec in specs.items():
        if name == "nvim":
            target = home / ".config/nvim"
            if target.exists() or target.is_symlink():
                print(f"Keep existing Neovim repository: {target}")
                continue
            source = checkout(name, spec, home / ".local/share/thomas-config")
            run(["git", "-C", source, "apply", ROOT / "nvim-image.patch"])
            link(source, target)
            continue
        output = outputs.get(name, home / ".tmux/plugins" / name)
        marker = markers / name
        if marker.exists() and marker.read_text() == spec["rev"] and output.exists():
            print(f"Already installed: {name}")
            continue
        source = checkout(name, spec, home / ".local/share/thomas-config")
        if name == "picom":
            options = ["--reconfigure"] if (source / "build/meson-private/coredata.dat").exists() else []
            run(["meson", "setup", *options, "build", "--buildtype=release", f"--prefix={prefix}"], cwd=source)
            run(["ninja", "-C", "build"], cwd=source)
            shutil.copy2(source / "build/src/picom", output)
        elif name == "dunst":
            run(["make", "-j2", "WAYLAND=0", "X11=1", "DUNSTIFY=0", "dunst"], cwd=source)
            shutil.copy2(source / "dunst", output)
            shutil.copy2(source / "dunstctl", binaries / "dunstctl")
        elif name == "eww":
            run(["cargo", "build", "--locked", "--release", "--no-default-features", "--features", "x11"], cwd=source)
            shutil.copy2(source / "target/release/eww", output)
        elif name == "blesh":
            run(["make", "install", f"PREFIX={prefix}"], cwd=source)
        elif name == "i3lock-color":
            run(["autoreconf", "-fiv"], cwd=source)
            build = source / "build"
            build.mkdir(exist_ok=True)
            run(["../configure", f"--prefix={prefix}", "--sysconfdir=/etc"], cwd=build)
            run(["make", "-j2"], cwd=build)
            shutil.copy2(build / "i3lock", output)
            # The distro i3lock package supplies /etc/pam.d/i3lock.
        elif name == "betterlockscreen":
            shutil.copy2(source / "betterlockscreen", output)
            output.chmod(0o755)
        else:
            link(source, output)
        marker.write_text(spec["rev"])

    xidlehook = home / ".cargo/bin/xidlehook"
    if not xidlehook.exists() or not (xidlehook.parent / "xidlehook-client").exists():
        run(["cargo", "install", "--locked", "--root", home / ".cargo", "xidlehook", "--version", "0.10.0"])


def assets(home, cache):
    for spec in json.loads((ROOT / "assets.json").read_text()):
        destination = home / ".local/share" / spec["kind"] / spec.get("installed", spec["name"])
        marker = cache / (spec["name"] + ".sha256")
        if destination.exists() and marker.exists() and marker.read_text() == spec["sha256"]:
            continue
        archive = cache / Path(spec["url"]).name
        if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != spec["sha256"]:
            run(["curl", "-fL", "--retry", "2", spec["url"], "-o", archive])
        if hashlib.sha256(archive.read_bytes()).hexdigest() != spec["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {archive}")
        if spec["kind"] == "fonts":
            destination.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive) as font_archive:
                for member in font_archive.getmembers():
                    if member.isfile() and (member.name.endswith(".otf") or Path(member.name).name.startswith("LICENSE")):
                        (destination / Path(member.name).name).write_bytes(font_archive.extractfile(member).read())
        else:
            unpacked = cache / (spec["name"] + "-unpacked")
            run(["dpkg-deb", "-x", archive, unpacked])
            # Extract assets only, without running maintainer scripts or adding an APT repository.
            source = unpacked / "usr/share" / spec["kind"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            for item in source.iterdir():
                target = destination.parent / item.name
                if target.exists() or target.is_symlink():
                    continue
                if item.is_symlink():
                    target.symlink_to(os.readlink(item))
                elif item.is_dir():
                    shutil.copytree(item, target, symlinks=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
            if not destination.exists():
                raise RuntimeError(f"Appearance archive is missing {destination.name}")
        marker.write_text(spec["sha256"])
    run(["fc-cache", "-f"])
