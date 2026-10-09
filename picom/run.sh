#!/bin/bash
# Supervise picom: 10.2 can abort on a map_win_start assert, which drops blur,
# corners and transparency until restarted. i3 exec_always calls this on every
# reload, so replace any previous supervisor first.
pidfile="${XDG_RUNTIME_DIR:-/tmp}/picom-run.pid"
[ -f "$pidfile" ] && kill "$(cat "$pidfile")" 2>/dev/null
echo $$ > "$pidfile"
pkill -x picom

# Prefer the self-built picom 12 (animations, fixed window state); fall back to the distro one.
picom=$HOME/.local/bin/picom
[ -x "$picom" ] || picom=picom

# ponytail: fixed 1s retry, no backoff; a broken config just retries quietly.
while true; do
    "$picom" --config "$(dirname "$(readlink -f "$0")")/picom.conf"
    sleep 1
done
