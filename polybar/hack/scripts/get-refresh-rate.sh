#!/bin/bash

# Get primary monitor
MONITOR=$(xrandr --current | grep " connected primary" | awk '{print $1}')
MONITOR=${MONITOR:-$(xrandr --current | grep " connected" | head -n1 | awk '{print $1}')}

# Get current refresh rate (look at the line AFTER the monitor line)
CURRENT=$(xrandr --current | grep "^$MONITOR connected" -A 1 | grep -oP '\d+\.\d+(?=\*)')

if [[ -n "$CURRENT" ]]; then
    OUTPUT="${CURRENT%.*}Hz"
else
    OUTPUT="N/A"
fi

# Send the IPC message for updates, and hide the command's output
polybar-msg action refresh-rate send "$OUTPUT" >/dev/null 2>&1

# Echo the value for the initial display
echo "$OUTPUT"
