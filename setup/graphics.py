"""Explicit, optional PRIME selection using distribution-provided drivers."""

from pathlib import Path
import shutil
import subprocess


def configure(profile, run):
    if profile not in ('on-demand', 'nvidia'):
        raise RuntimeError('Unsupported PRIME profile')
    prime = shutil.which('prime-select')
    if not prime:
        raise RuntimeError('Install nvidia-prime with setup.sh apply, and GPU drivers with the distribution tools')
    vendors = set()
    for device in Path('/sys/bus/pci/devices').glob('*'):
        if (device / 'class').read_text().startswith('0x03'):
            vendors.add((device / 'vendor').read_text().strip())
    if not {'0x8086', '0x10de'}.issubset(vendors):
        raise RuntimeError('This optional graphics setup requires Intel and NVIDIA graphics')
    current = subprocess.check_output([prime, 'query'], text=True, timeout=10).strip()
    if current != profile:
        run(['sudo', prime, profile])
        if subprocess.check_output([prime, 'query'], text=True, timeout=10).strip() != profile:
            raise RuntimeError('PRIME profile did not apply; inspect prime-select output before logging out')
    print(f'PRIME profile selected: {profile}. This does not verify the current desktop renderer.')
    print('Save work, then log out and back in. Setup does not end your session or reboot.')
    print('Verify with glxinfo -B and xrandr --listproviders; see README.md for offload and rollback.')
