"""Install the fixed battery-mode helper and its Polkit action."""

from datetime import datetime
from pathlib import Path
import os
import stat

ROOT = Path(__file__).resolve().parent
FILES = [
    (ROOT / 'battery-power.py', Path('/usr/local/libexec/thomas-battery-power'), 0o755),
    (ROOT / 'polkit/org.thomas.battery-mode.policy',
     Path('/usr/share/polkit-1/actions/org.thomas.battery-mode.policy'), 0o644),
]
LINK = Path('/etc/tlp.d/99-thomas-battery-mode.conf')
TARGET = Path('/run/thomas-battery-mode/tlp.conf')


def matches(source, target, mode):
    try:
        info = target.lstat()
        return (stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and stat.S_IMODE(info.st_mode) == mode and target.read_bytes() == source.read_bytes())
    except FileNotFoundError:
        return False


def safe_parent(target):
    for parent in target.parent.resolve().parents:
        if parent.exists():
            info = parent.stat()
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise RuntimeError(f'Battery helper needs root-owned system directories: {parent}')
    parent = target.parent
    if parent.exists() and (parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022):
        raise RuntimeError(f'Battery helper directory is writable by other users: {parent}')


def check():
    gaps = [f'battery helper: {target}' for source, target, mode in FILES if not matches(source, target, mode)]
    if not LINK.is_symlink() or os.readlink(LINK) != str(TARGET) or LINK.lstat().st_uid != 0:
        gaps.append('battery helper: TLP runtime link')
    return gaps


def install(run):
    if not Path('/usr/sbin/tlp').is_file():
        print('Pending: install desktop dependencies with setup.sh apply for Battery Saver.')
        return
    backup = Path('/var/backups/thomas-config') / datetime.now().strftime('%Y%m%d-%H%M%S-%f')

    def preserve(target):
        safe_parent(target)
        if target.is_dir() and not target.is_symlink():
            raise RuntimeError(f'Expected a file, preserved existing directory: {target}')
        if target.exists() or target.is_symlink():
            saved = backup / target.relative_to('/')
            run(['sudo', 'install', '-d', '-m', '755', saved.parent])
            run(['sudo', 'cp', '-a', target, saved])
            print(f'Backup: {target} -> {saved}')

    for source, target, mode in FILES:
        if not matches(source, target, mode):
            preserve(target)
            if target.is_symlink():
                run(['sudo', 'rm', '--', target])
            run(['sudo', 'install', '-D', '-o', 'root', '-g', 'root', '-m', f'{mode:o}', source, target])
    if not LINK.is_symlink() or os.readlink(LINK) != str(TARGET) or LINK.lstat().st_uid != 0:
        preserve(LINK)
        run(['sudo', 'install', '-d', '-m', '755', LINK.parent])
        if LINK.exists() or LINK.is_symlink():
            run(['sudo', 'rm', '--', LINK])
        run(['sudo', 'ln', '-s', TARGET, LINK])
