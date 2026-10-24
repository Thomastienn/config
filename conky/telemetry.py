#!/usr/bin/env python3
"""Read hardware sensors for the system panel without waking a sleeping GPU."""

import math
from pathlib import Path
import subprocess


HWMON = Path('/sys/class/hwmon')
PCI = Path('/sys/bus/pci/devices')


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def number(text, maximum):
    try:
        value = float(text)
        return value if math.isfinite(value) and 0 <= value <= maximum else None
    except ValueError:
        return None


def cpu_temperature():
    packages, controls = [], []
    for device in HWMON.glob('hwmon*'):
        if read(device / 'name') not in ('coretemp', 'k10temp', 'zenpower'):
            continue
        for sensor in device.glob('temp*_input'):
            label = read(sensor.with_name(sensor.name.replace('_input', '_label')))
            value = number(read(sensor), 150000)
            if value is None:
                continue
            if label.startswith('Package id ') or label == 'Tdie':
                packages.append(value / 1000)
            elif label == 'Tctl':
                controls.append(value / 1000)
    return max(packages or controls, default=None)


def gpu():
    # shortcut: Show the first NVIDIA adapter; add per-device meters for a multi-GPU host.
    for device in sorted(PCI.glob('*')):
        if read(device / 'vendor') != '0x10de' or not read(device / 'class').startswith('0x03'):
            continue
        state = read(device / 'power/runtime_status')
        if state in ('suspended', 'suspending'):
            return 'sleep', None
        if state not in ('active', 'unsupported'):
            return None, None
        try:
            result = subprocess.run(
                ['nvidia-smi', '--id=' + device.name,
                 '--query-gpu=utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True, timeout=2,
            )
            usage, temperature = result.stdout.strip().split(',')
            return number(usage, 100), number(temperature, 150)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None, None
    return None, None


def main():
    usage, temperature = gpu()
    values = (cpu_temperature(), usage, temperature)
    print('${lua telemetry ' + ' '.join('-' if v is None else str(v) for v in values) + '}')


if __name__ == '__main__':
    main()
