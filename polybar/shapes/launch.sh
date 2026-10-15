#!/usr/bin/env bash

# Polybar launch script - handles i3 reload gracefully

DIR="$HOME/.config/polybar/shapes"

# Power-supply names differ between laptops.
for supply in /sys/class/power_supply/*; do
    [[ -r "$supply/type" ]] || continue
    case $(cat "$supply/type") in
        Battery) export THOMAS_BATTERY=${THOMAS_BATTERY:-${supply##*/}} ;;
        Mains) export THOMAS_ADAPTER=${THOMAS_ADAPTER:-${supply##*/}} ;;
    esac
done

# Terminate existing polybar with timeout
if pgrep -x polybar >/dev/null 2>&1; then
    # Send SIGTERM first
    pkill -TERM -x polybar 2>/dev/null
    
    # Wait up to 2 seconds
    for _ in {1..20}; do
        pgrep -x polybar >/dev/null 2>&1 || break
        sleep 0.1
    done
    
    # Force kill if still running
    pkill -KILL -x polybar 2>/dev/null
    sleep 0.2
fi

# Launch polybar
polybar -q main -c "$DIR/config.ini" &

disown
