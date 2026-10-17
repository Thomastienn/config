#!/bin/bash
# Supervise picom: 10.2 can abort on a map_win_start assert, which drops blur,
# corners and transparency until restarted. i3 exec_always calls this on every
# reload, so replace any previous supervisor first.
directory=$(dirname "$(readlink -f "$0")")
runtime=${XDG_RUNTIME_DIR:-/run/user/$UID}
pidfile="$runtime/picom-run.pid"
# Serialize launches and replace only this supervisor's compositor.
exec 9>"$runtime/picom-start.lock"
flock 9
if [[ -f $pidfile ]]; then
    previous=$(cat "$pidfile")
    if [[ $previous =~ ^[0-9]+$ ]] &&
       [[ $(stat -c %u "/proc/$previous" 2>/dev/null) == "$UID" ]] &&
       tr '\0' '\n' < "/proc/$previous/cmdline" 2>/dev/null |
           grep -Fxq -e "$directory/run.sh" -e "$HOME/thomas_config/picom/run.sh" -e "$HOME/.config/picom/run.sh"; then
        children=$(cat "/proc/$previous/task/$previous/children" 2>/dev/null)
        kill "$previous" 2>/dev/null
        for process in $children; do
            if [[ $(stat -c %u "/proc/$process" 2>/dev/null) == "$UID" ]] &&
               [[ $(cat "/proc/$process/comm" 2>/dev/null) == picom ]]; then
                kill "$process" 2>/dev/null
            fi
        done
    fi
fi
echo $$ > "$pidfile"
flock -u 9
exec 9>&-
cleanup() {
    [[ -n ${child:-} ]] && kill "$child" 2>/dev/null
    [[ $(cat "$pidfile" 2>/dev/null) == "$$" ]] && rm -f "$pidfile"
}
trap cleanup EXIT
trap 'exit 0' TERM INT

# Prefer the self-built picom 12 (animations, fixed window state); fall back to the distro one.
picom=$HOME/.local/bin/picom
[ -x "$picom" ] || picom=picom

# shortcut: fixed 1s retry; inspect the runtime log if a config repeatedly fails.
while true; do
    config="$directory/picom.conf"
    [[ -f $runtime/thomas-battery-mode/active ]] && config="$directory/battery.conf"
    "$picom" --config "$config" &
    child=$!
    wait "$child"
    child=
    sleep 1
done
