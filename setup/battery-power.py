#!/usr/bin/python3 -I
"""Fixed privileged operations for the desktop battery toggle. Installed as root."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path('/run/thomas-battery-mode')
STATE = ROOT / 'power.json'
CONFIG = ROOT / 'tlp.conf'
LINK = Path('/etc/tlp.d/99-thomas-battery-mode.conf')
# Brave watches only /etc; tmpfiles.d removes this at boot like the /run state.
BRAVE = Path('/etc/brave/policies/managed/thomas-battery-mode.json')
SYS = Path('/sys')
TLP = '/usr/sbin/tlp'


def read(path):
    return path.read_text().strip()


def save(path, value):
    fd, temporary = tempfile.mkstemp(dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else None


def apply_tlp():
    manual = Path('/run/tlp/manual_mode')
    mode = {'0': 'ac', '1': 'bat'}.get(read(manual), 'start') if manual.exists() else 'start'
    result = subprocess.run([TLP, mode], capture_output=True, text=True, timeout=45,
                            env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    if result.returncode:
        raise RuntimeError('TLP failed: ' + (result.stderr or result.stdout).strip()[-1200:])


def targets():
    values, settings, skipped = {}, {}, []

    def setting(name, value):
        settings[name + '_ON_AC'] = value
        settings[name + '_ON_BAT'] = value

    def target(path, value):
        values[str(path)] = {'before': read(path), 'applied': value}

    profile = SYS / 'firmware/acpi/platform_profile'
    choices = profile.with_name('platform_profile_choices')
    if choices.exists():
        low = next((name for name in ('quiet', 'low-power') if name in read(choices).split()), None)
        if low:
            target(profile, low)
            setting('PLATFORM_PROFILE', low)
    if str(profile) not in values:
        skipped.append('Quiet platform profile unavailable')

    policies = sorted((SYS / 'devices/system/cpu/cpufreq').glob('policy*'))
    # Generic "powersave" governors can pin a CPU at minimum speed.
    compatible = policies and all(read(p / 'scaling_driver') in ('intel_pstate', 'amd-pstate-epp')
                                  for p in policies)
    if compatible and all('powersave' in read(p / 'scaling_available_governors').split() for p in policies):
        setting('CPU_SCALING_GOVERNOR', 'powersave')
        for policy in policies:
            target(policy / 'scaling_governor', 'powersave')
    if policies and all((p / 'energy_performance_available_preferences').exists()
                        and 'power' in read(p / 'energy_performance_available_preferences').split()
                        for p in policies):
        setting('CPU_ENERGY_PERF_POLICY', 'power')
        for policy in policies:
            target(policy / 'energy_performance_preference', 'power')
    else:
        skipped.append('CPU energy preference unavailable')

    no_turbo = SYS / 'devices/system/cpu/intel_pstate/no_turbo'
    boost = SYS / 'devices/system/cpu/cpufreq/boost'
    if no_turbo.exists() or boost.exists():
        target(no_turbo if no_turbo.exists() else boost, '1' if no_turbo.exists() else '0')
        setting('CPU_BOOST', '0')
    else:
        skipped.append('CPU turbo control unavailable')
    dynamic = SYS / 'devices/system/cpu/intel_pstate/hwp_dynamic_boost'
    if dynamic.exists():
        target(dynamic, '0')
        setting('CPU_HWP_DYN_BOOST', '0')
    maximum = SYS / 'devices/system/cpu/intel_pstate/max_perf_pct'
    minimum = maximum.with_name('min_perf_pct')
    if maximum.exists() and minimum.exists() and int(read(minimum)) <= 40:
        ceiling = str(min(40, int(read(maximum))))
        target(maximum, ceiling)
        setting('CPU_MAX_PERF', ceiling)
    else:
        skipped.append('40% Intel CPU performance ceiling unavailable')
    if not values:
        raise RuntimeError('No supported CPU or platform power controls')
    return values, settings, skipped


def restore(state, force=False):
    state['phase'] = 'restoring'
    save(STATE, json.dumps(state))
    CONFIG.unlink(missing_ok=True)
    BRAVE.unlink(missing_ok=True)
    manual, errors = {}, []
    for name, value in state['values'].items():
        path = Path(name)
        if not path.exists():
            continue
        try:
            current = read(path)
            if force or current == value['applied']:
                path.write_text(value['before'])
            elif current != value['before']:
                manual[path] = current
        except OSError as error:
            errors.append(str(error))
    try:
        apply_tlp()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    for path, value in manual.items():
        try:
            path.write_text(value)
        except OSError as error:
            errors.append(str(error))
    if errors:
        raise RuntimeError('Power restoration incomplete: ' + '; '.join(errors))
    STATE.unlink(missing_ok=True)


def switch(action, uid):
    state = load()
    if state and uid not in (0, state['uid']):
        raise RuntimeError('Battery mode belongs to another logged-in user')
    if action == 'off':
        if state:
            restore(state)
        return
    if state and state['phase'] == 'enabled':
        return
    if state:
        restore(state, force=True)
    if not LINK.is_symlink() or LINK.resolve() != CONFIG:
        raise RuntimeError('Battery power helper is not configured; rerun setup.sh apply')
    for service in ('power-profiles-daemon', 'auto-cpufreq', 'tuned'):
        result = subprocess.run(['/usr/bin/systemctl', 'is-active', '--quiet', service], timeout=5)
        if result.returncode == 0:
            raise RuntimeError(f'{service} conflicts with TLP; choose one power manager first')
    values, settings, skipped = targets()
    state = {'uid': uid, 'phase': 'applying', 'values': values, 'skipped': skipped}
    save(STATE, json.dumps(state))
    try:
        save(CONFIG, '# Temporary battery-mode overrides; cleared at reboot.\n' +
             ''.join(f'{key}="{value}"\n' for key, value in settings.items()))
        apply_tlp()
        wrong = [name for name, value in values.items() if read(Path(name)) != value['applied']]
        if wrong:
            raise RuntimeError('Power settings did not apply; check explicit /etc/tlp.conf overrides: ' + ', '.join(wrong))
        if Path('/opt/brave.com/brave').is_dir():
            BRAVE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            # 2 = Energy Saver whenever unplugged; Brave has no always-on value.
            BRAVE.write_text('{"BatterySaverModeAvailability": 2}\n')
        state['phase'] = 'enabled'
        save(STATE, json.dumps(state))
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        try:
            restore(state, force=True)
        except (OSError, RuntimeError, subprocess.SubprocessError) as rollback:
            raise RuntimeError(f'{error}; {rollback}') from error
        raise


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('on', 'off'):
        raise RuntimeError('Usage: thomas-battery-power on|off')
    if os.geteuid() != 0:
        raise RuntimeError('Run through the installed Polkit action')
    uid = int(os.environ.get('PKEXEC_UID', os.environ.get('SUDO_UID', '0')))
    ROOT.mkdir(mode=0o755, exist_ok=True)
    info = ROOT.lstat()
    if ROOT.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('Unsafe battery-mode runtime directory')
    with (ROOT / 'power.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        switch(sys.argv[1], uid)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
