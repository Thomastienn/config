"""Install compressed RAM swap (zram) ahead of the disk swapfile."""

from datetime import datetime
from pathlib import Path

from power import matches, safe_parent

ROOT = Path(__file__).resolve().parent
GENERATOR = Path('/usr/lib/systemd/system-generators/zram-generator')
SYSCTL = Path('/etc/sysctl.d/99-thomas-zram.conf')
FILES = [
    (ROOT / 'zram/zram-generator.conf', Path('/etc/systemd/zram-generator.conf'), 0o644),
    (ROOT / 'zram/sysctl.conf', SYSCTL, 0o644),
]


def active():
    return any(line.startswith('/dev/zram') for line in Path('/proc/swaps').read_text().splitlines())


def check():
    gaps = [f'zram: {target}' for source, target, mode in FILES if not matches(source, target, mode)]
    if not active():
        gaps.append('zram: swap not active')
    return gaps


def install(run):
    if not GENERATOR.is_file():
        print('Pending: install desktop dependencies with setup.sh apply for zram swap.')
        return
    backup = Path('/var/backups/thomas-config') / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for source, target, mode in FILES:
        if matches(source, target, mode):
            continue
        safe_parent(target)
        if target.exists() or target.is_symlink():
            saved = backup / target.relative_to('/')
            run(['sudo', 'install', '-d', '-m', '755', saved.parent])
            run(['sudo', 'cp', '-a', target, saved])
            print(f'Backup: {target} -> {saved}')
            if target.is_symlink():
                run(['sudo', 'rm', '--', target])
        run(['sudo', 'install', '-D', '-o', 'root', '-g', 'root', '-m', f'{mode:o}', source, target])
    run(['sudo', 'sysctl', '-q', '-p', SYSCTL])
    if not active():
        run(['sudo', 'systemctl', 'daemon-reload'])
        run(['sudo', 'systemctl', 'start', 'dev-zram0.swap'])
    # A running zram device keeps its size until reboot; setup never swaps it off under load.
