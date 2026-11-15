#!/bin/bash
# Idle warning from xidlehook: idle-dim.sh 0.5 dims every output, idle-dim.sh 1 restores.
# Software brightness (gamma), so Battery Saver's backlight levels stay untouched.
# xidlehook spawns dim and restore without waiting, so a slow dim could land after the
# restore and stick. Serialize them, and turn a dim into a restore once the user is back
# (dims only fire after 100+ s idle, so under 10 s idle means activity since then).
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/thomas-idle-dim.lock"
flock 9
if [ "${1:-1}" != 1 ] && [ "$(xssstate -i)" -lt 10000 ]; then
    set -- 1
fi
for output in $(xrandr --current | awk '/ connected/ {print $1}'); do
    xrandr --output "$output" --brightness "${1:-1}"
done
