#!/bin/bash
# Idle warning from xidlehook: idle-dim.sh 0.5 dims every output, idle-dim.sh 1 restores.
# Software brightness (gamma), so Battery Saver's backlight levels stay untouched.
for output in $(xrandr --current | awk '/ connected/ {print $1}'); do
    xrandr --output "$output" --brightness "${1:-1}"
done
