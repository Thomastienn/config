#!/usr/bin/env python3
"""Reversible battery mode for the existing i3 desktop."""

import fcntl
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
ROOT = RUNTIME / 'thomas-battery-mode'
STATE = ROOT / 'desktop.json'
ACTIVE = ROOT / 'active'
ERROR = ROOT / 'error'
POWER = Path('/run/thomas-battery-mode/power.json')
HELPER = Path('/usr/local/libexec/thomas-battery-power')
SYS = Path('/sys')
PDF_TIMER = 'thomas-pdf-index.timer'


def capture(args, timeout=10):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or f'{args[0]} failed')
    return result.stdout.strip()


def load(path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def save(state):
    fd, temporary = tempfile.mkstemp(dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, STATE)
    finally:
        Path(temporary).unlink(missing_ok=True)


def backend_active():
    state = load(POWER)
    return bool(state and state['uid'] == os.getuid() and state['phase'] == 'enabled')


def helper_ready():
    try:
        return HELPER.read_bytes() == (REPO / 'setup/battery-power.py').read_bytes()
    except OSError:
        return False


def displays():
    result, current = {}, None
    for line in capture(['xrandr', '--current']).splitlines():
        if line and not line[0].isspace():
            name = line.split()[0]
            current = name if re.match(r'(?i)^(edp|lvds|dsi)', name) and ' connected ' in line else None
        elif current:
            fields = line.split()
            if len(fields) < 2:
                continue
            rates = [match.groups() for field in fields[1:]
                     if (match := re.fullmatch(r'(\d+(?:\.\d+)?)([+*]*)', field))]
            active = next((rate for rate, flags in rates if '*' in flags), None)
            if active:
                low = next((rate for rate, _ in rates if abs(float(rate) - 60) <= 1), None)
                result[current] = {'mode': fields[0], 'rate': active, 'low': low}
    return result


def same_rate(left, right):
    return abs(float(left) - float(right)) < 0.1


def set_rate(name, mode, rate):
    capture(['xrandr', '--output', name, '--mode', mode, '--rate', rate])
    actual = displays().get(name)
    if not actual or actual['mode'] != mode or not same_rate(actual['rate'], rate):
        raise RuntimeError(f'{name}: refresh rate did not apply')


def lights():
    result = []
    backlights = SYS / 'class/backlight'
    preferred = os.environ.get('THOMAS_BACKLIGHT', 'nvidia_wmi_ec_backlight')
    if not re.fullmatch(r'[\w:.-]+', preferred):
        raise RuntimeError('Invalid backlight device name')
    device = backlights / preferred
    if not device.is_dir() and backlights.exists() and any(backlights.iterdir()):
        name = capture(['brightnessctl', '-c', 'backlight', '-m']).splitlines()[0].split(',')[0]
        device = backlights / name
    if device.is_dir():
        maximum = int((device / 'max_brightness').read_text())
        before = int((device / 'brightness').read_text())
        result.append({'device': device.name, 'path': str(device / 'brightness'),
                       'before': before, 'applied': min(before, max(1, maximum * 20 // 100))})
    for device in sorted((SYS / 'class/leds').glob('*kbd_backlight*')):
        result.append({'device': device.name, 'path': str(device / 'brightness'),
                       'before': int((device / 'brightness').read_text()), 'applied': 0})
    return result


def set_light(light, value):
    if int(Path(light['path']).read_text()) != value:
        capture(['brightnessctl', '-q', '-d', light['device'], 'set', str(value)])
    if int(Path(light['path']).read_text()) != value:
        raise RuntimeError(f"{light['device']}: brightness did not apply")


def same_display(pid):
    return ('DISPLAY=' + os.environ.get('DISPLAY', '')).encode() in (Path('/proc') / str(pid) / 'environ').read_bytes().split(b'\0')


def conky_processes():
    result = {}
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid() or (process / 'comm').read_text().strip() != 'conky':
                continue
            command = (process / 'cmdline').read_bytes()
            args = command.decode().split('\0')
            if '-c' not in args or not same_display(process.name):
                continue
            config = Path(args[args.index('-c') + 1])
            if not (REPO / 'conky' / config.name).is_file():
                continue
            source = config.read_text()
            # Also recognize configs generated before the launcher added ownership markers.
            if (f'-- thomas-conky: {REPO}\n' in source or
                    '/thomas_config/conky/' in source or str(REPO / 'conky') + '/' in source):
                result[int(process.name)] = (config.name, command)
        except (OSError, ValueError, IndexError):
            continue
    return result


def stop_conky():
    descriptors = []
    try:
        for pid, previous in conky_processes().items():
            try:
                descriptor = os.pidfd_open(pid)
                if conky_processes().get(pid) == previous:
                    descriptors.append(descriptor)
                    signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                else:
                    os.close(descriptor)
            except ProcessLookupError:
                continue
        if descriptors:
            pending = set(descriptors)
            deadline = time.monotonic() + 3
            while pending:
                finished, _, _ = select.select(list(pending), [], [], max(0, deadline - time.monotonic()))
                if not finished:
                    raise RuntimeError('Managed Conky did not stop')
                pending.difference_update(finished)
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def unit_active(name):
    return subprocess.run(['systemctl', '--user', 'is-active', '--quiet', name],
                          capture_output=True, timeout=5).returncode == 0


def pause_extras():
    # Serialize with the launcher so an i3 reload cannot start panels after this stop.
    with (RUNTIME / 'conky-start.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop_conky()
    if unit_active(PDF_TIMER):
        capture(['systemctl', '--user', 'stop', PDF_TIMER])


def idle_ready():
    try:
        text = capture([Path.home() / '.cargo/bin/xidlehook-client', '--socket',
                        RUNTIME / 'thomas-xidlehook.sock', 'query'], timeout=2)
        return 'battery-mode.py' in text and 'idle-blank' in text
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return False


def idle_blank():
    if not ACTIVE.exists() or not backend_active():
        return
    import afk
    from gi.repository import Gio, GLib

    if afk.active():
        return
    # An unavailable inhibitor check must leave the display on.
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        inhibited = bus.call_sync('org.freedesktop.login1', '/org/freedesktop/login1',
                                 'org.freedesktop.DBus.Properties', 'Get',
                                 GLib.Variant('(ss)', ('org.freedesktop.login1.Manager', 'BlockInhibited')),
                                 None, Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
    except GLib.Error as error:
        raise RuntimeError('Idle blanking skipped: inhibitor check failed') from error
    if 'idle' in inhibited.split(':'):
        return
    if 'DPMS is Enabled' not in capture(['xset', 'q']):
        raise RuntimeError('Idle blanking skipped: DPMS is disabled or unavailable')
    capture(['xset', 'dpms', 'force', 'off'])


def gpu_detail():
    states = []
    for device in (SYS / 'bus/pci/devices').glob('*'):
        try:
            if ((device / 'vendor').read_text().strip() == '0x10de' and
                    (device / 'class').read_text().startswith('0x03')):
                states.append((device / 'power/runtime_status').read_text().strip())
        except OSError:
            continue
    return 'NVIDIA ' + '/'.join(sorted(set(states))) if states else ''


def refresh_visuals():
    pidfile = RUNTIME / 'picom-run.pid'
    if pidfile.exists():
        from Xlib import X, display as xdisplay
        from Xlib.error import DisplayConnectionError, XError

        try:
            connection = xdisplay.Display()
        except DisplayConnectionError as error:
            raise RuntimeError('Cannot verify the Picom compositor: ' + str(error)) from error
        logfile = ROOT / 'picom.log'
        try:
            with logfile.open('ab') as log:
                supervisor = subprocess.Popen([str(REPO / 'picom/run.sh')], stdout=log, stderr=log,
                                              start_new_session=True)
            expected = str(REPO / 'picom' / ('battery.conf' if ACTIVE.exists() else 'picom.conf'))
            selection = connection.intern_atom('_NET_WM_CM_S' + str(connection.get_default_screen()))
            pid_atom = connection.intern_atom('_NET_WM_PID')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    owner = connection.get_selection_owner(selection)
                    owner_pid = owner.get_full_property(pid_atom, X.AnyPropertyType) if owner else None
                    children = (Path('/proc') / str(supervisor.pid) / 'task' / str(supervisor.pid) / 'children').read_text().split()
                    for pid in children:
                        command = (Path('/proc') / pid / 'cmdline').read_bytes().split(b'\0')
                        # A briefly alive process may still fail because another compositor owns the screen.
                        if expected.encode() in command and owner_pid is not None and list(owner_pid.value) == [int(pid)]:
                            time.sleep(0.25)
                            if (connection.get_selection_owner(selection) == owner and
                                    (Path('/proc') / pid / 'cmdline').read_bytes().split(b'\0') == command):
                                return
                except (FileNotFoundError, XError):
                    pass
                if supervisor.poll() is not None:
                    break
                time.sleep(0.1)
            raise RuntimeError('Picom did not take over compositing; see ' + str(logfile))
        finally:
            connection.close()


def power(action):
    if not HELPER.is_file():
        raise RuntimeError('Battery Saver needs installation: run setup.sh apply')
    capture(['pkexec', HELPER, action], timeout=60)


def snapshot():
    found = displays()
    state = {'phase': 'applying', 'displays': {}, 'lights': lights(), 'skipped': [], 'display_issues': [],
             'conky': sorted({name for name, _ in conky_processes().values()}),
             'pdf_timer': unit_active(PDF_TIMER)}
    if not any('/backlight/' in light['path'] for light in state['lights']):
        state['skipped'].append('Display brightness unavailable')
    for name, display in found.items():
        if display['low'] is None:
            state['display_issues'].append(f'{name}: 60 Hz unavailable')
        else:
            state['displays'][name] = {'mode': display['mode'], 'before': display['rate'],
                                       'applied': display['low'], 'override': False}
    if not found:
        state['display_issues'].append('No active internal display')
    return state


def restore_desktop(state, force=False):
    errors = []
    state['phase'] = 'restoring'
    save(state)
    try:
        current = displays()
        for name, old in state['displays'].items():
            display = current.get(name)
            if display and display['mode'] == old['mode'] and (force or same_rate(display['rate'], old['applied'])):
                set_rate(name, old['mode'], old['before'])
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    for light in state['lights']:
        try:
            path = Path(light['path'])
            if path.exists() and (force or int(path.read_text()) == light['applied']):
                set_light(light, light['before'])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    ACTIVE.unlink(missing_ok=True)
    try:
        refresh_visuals()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    try:
        panels = state.get('conky', [])
        if panels:
            capture([REPO / 'conky/run.sh', *panels])
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    try:
        if state.get('pdf_timer'):
            capture(['systemctl', '--user', 'start', PDF_TIMER])
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        errors.append(str(error))
    if errors:
        raise RuntimeError('Desktop restoration incomplete: ' + '; '.join(errors))
    STATE.unlink(missing_ok=True)


def off():
    state = load(POWER)
    if state and state['uid'] == os.getuid():
        power('off')
    desktop = load(STATE)
    if desktop:
        restore_desktop(desktop)
    else:
        ACTIVE.unlink(missing_ok=True)
        refresh_visuals()


def on():
    state = load(STATE)
    if state and state['phase'] == 'enabled' and backend_active():
        return
    if state:
        off()
    # Root power state outlives logout; re-applying the desktop then needs no pkexec.
    elevate = not backend_active()
    if elevate and not helper_ready():
        raise RuntimeError('Battery Saver needs the updated helper: run setup.sh apply')
    state = snapshot()
    save(state)
    try:
        if elevate:
            power('on')
        for name, display in state['displays'].items():
            set_rate(name, display['mode'], display['applied'])
        for light in state['lights']:
            set_light(light, light['applied'])
        ACTIVE.write_text('1\n')
        pause_extras()
        refresh_visuals()
        state['phase'] = 'enabled'
        save(state)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        failures = [str(error)]
        try:
            root = load(POWER)
            if root and root['uid'] == os.getuid():
                power('off')
        except (OSError, RuntimeError, subprocess.SubprocessError) as rollback:
            failures.append(str(rollback))
        try:
            restore_desktop(state, force=True)
        except (OSError, RuntimeError, subprocess.SubprocessError) as rollback:
            failures.append(str(rollback))
        raise RuntimeError('; '.join(failures)) from error


def reconcile(resume=False):
    if not backend_active():
        state = load(STATE)
        if state:
            restore_desktop(state)
        return
    state = load(STATE)
    if not state:
        on()
        return
    if state['phase'] != 'enabled':
        return
    if 'conky' in state:
        pause_extras()
    current = displays()
    state['display_issues'] = [f'{name}: 60 Hz unavailable' for name, display in current.items()
                               if display['low'] is None]
    if not current:
        state['display_issues'].append('No active internal display')
    for name, display in current.items():
        old = state['displays'].get(name)
        if not old:
            if display['low'] is None:
                continue
            old = {'mode': display['mode'], 'before': display['rate'], 'applied': display['low'], 'override': False}
            state['displays'][name] = old
            save(state)
            set_rate(name, old['mode'], old['applied'])
        elif old['mode'] != display['mode']:
            old['override'] = True
        elif resume and not old['override']:
            set_rate(name, old['mode'], old['applied'])
        elif not same_rate(display['rate'], old['applied']):
            old['override'] = True
    save(state)


def status():
    desktop, root = load(STATE), load(POWER)
    enabled = bool(desktop and desktop['phase'] == 'enabled' and ACTIVE.exists())
    issues = list(desktop.get('skipped', [])) if desktop else []
    if desktop:
        issues.extend(desktop.get('display_issues', []))
    if root and root['uid'] == os.getuid():
        issues.extend(root.get('skipped', []))
        if root['phase'] != 'enabled':
            issues.append('Power restoration needs attention')
        elif enabled:
            for name, value in root['values'].items():
                try:
                    if Path(name).read_text().strip() != value['applied']:
                        issues.append('CPU or platform setting adjusted')
                        break
                except OSError:
                    issues.append('Power control unavailable')
                    break
        else:
            issues.append('CPU limits still on; toggle to turn off')
    elif enabled:
        issues.append('Power settings are not enabled')
    if ERROR.exists():
        issues.append(ERROR.read_text().strip())
    ready = helper_ready()
    available = HELPER.is_file() and (ready or enabled or backend_active())
    if not ready:
        issues.append('Run setup.sh apply to install or update Battery Saver')
    detail = 'On' if enabled else 'Off'
    if enabled:
        gpu = gpu_detail()
        if gpu:
            detail += ' · ' + gpu
        if not idle_ready():
            issues.append('Two-minute blanking needs logout/login')
    if enabled and any(value.get('override') for value in desktop['displays'].values()):
        detail += ' · display adjusted'
    if issues:
        detail += ' · ' + '; '.join(issues)
    return {'enabled': enabled, 'available': available, 'detail': detail, 'issues': issues}


def locked(action):
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (ROOT / 'desktop.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return action()


def run_session():
    from gi.repository import Gio, GLib
    from Xlib import display as xdisplay
    from Xlib.ext import randr

    connection = xdisplay.Display()
    randr.select_input(connection.screen().root, randr.RRScreenChangeNotifyMask |
                       randr.RRCrtcChangeNotifyMask | randr.RROutputChangeNotifyMask)
    connection.flush()
    loop = GLib.MainLoop()
    pending = None

    def update(resume=False):
        nonlocal pending
        pending = None
        try:
            locked(lambda: reconcile(resume))
            ERROR.unlink(missing_ok=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            ERROR.write_text(str(error))
            print(str(error), file=sys.stderr, flush=True)
        return False

    def events(_source, condition):
        nonlocal pending
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            loop.quit()
            return False
        while connection.pending_events():
            connection.next_event()
        if pending is None:
            pending = GLib.timeout_add(250, update)
        return True

    def sleep_changed(*args):
        nonlocal pending
        asleep = args[-2].unpack()[0]
        if not asleep:
            if pending is not None:
                GLib.source_remove(pending)
            pending = GLib.timeout_add(1000, update, True)

    locked(reconcile)
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus.signal_subscribe('org.freedesktop.login1', 'org.freedesktop.login1.Manager',
                         'PrepareForSleep', '/org/freedesktop/login1', None,
                         Gio.DBusSignalFlags.NONE, sleep_changed)
    GLib.io_add_watch(connection.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, events)
    try:
        loop.run()
    finally:
        connection.close()


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('on', 'off', 'toggle', 'status', 'run', 'session-start',
                                              'conky-stop', 'idle-blank'):
        raise RuntimeError('Usage: battery-mode.py on|off|toggle|status')
    action = sys.argv[1]
    if action == 'conky-stop':
        # The launcher owns conky-start.lock; taking it here would deadlock.
        stop_conky()
        return
    if action == 'idle-blank':
        idle_blank()
        return
    if action == 'status':
        print(json.dumps(status()))
        return
    if action == 'session-start':
        environment = [key for key in ('DISPLAY', 'XAUTHORITY', 'I3SOCK') if os.environ.get(key)]
        if environment:
            capture(['systemctl', '--user', 'import-environment', *environment])
        capture(['systemctl', '--user', 'restart', 'thomas-battery-mode.service'])
        return
    if action == 'run':
        run_session()
        return

    def change():
        selected = ('off' if ACTIVE.exists() or backend_active() else 'on') if action == 'toggle' else action
        (on if selected == 'on' else off)()
        ERROR.unlink(missing_ok=True)
    locked(change)
    print(json.dumps(status()))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        if ROOT.is_dir():
            ERROR.write_text(str(error))
        print(str(error), file=sys.stderr)
        if sys.argv[1:] and sys.argv[1] in ('on', 'off', 'toggle') and shutil.which('notify-send'):
            subprocess.run(['notify-send', '-a', 'Battery Saver', '-u', 'normal',
                            'Battery Saver', str(error)[:500]], timeout=5)
        sys.exit(1)
