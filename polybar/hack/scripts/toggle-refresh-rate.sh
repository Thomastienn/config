#!/bin/bash

# Get primary monitor
MONITOR=$(xrandr --current | grep " connected primary" | awk '{print $1}')
MONITOR=${MONITOR:-$(xrandr --current | grep " connected" | head -n1 | awk '{print $1}')}

RESOLUTION="1920x1080"
RATE_HIGH="144"
RATE_LOW="60"

# Get current refresh rate
CURRENT=$(xrandr --current | grep "^$MONITOR connected" -A 1 | grep -oP '\d+\.\d+(?=\*)')

if [[ -z "$CURRENT" ]]; then
    echo "Error: Monitor $MONITOR not found or not connected" >&2
    exit 1
fi

# Toggle logic
CURRENT_INT=${CURRENT%.*}  # Convert 144.00 -> 144
if [[ "$CURRENT_INT" -ge "$RATE_HIGH" ]]; then
    NEW_RATE="$RATE_LOW"
else
    NEW_RATE="$RATE_HIGH"
fi

# Apply change
if xrandr --output "$MONITOR" --mode "$RESOLUTION" --rate "$NEW_RATE" 2>/dev/null; then
    echo "Switched $MONITOR to ${NEW_RATE}Hz"
    
    # Notify polybar (if running)
    /home/thomas/thomas_config/polybar/hack/scripts/get-refresh-rate.sh
    
    # Optional: Send desktop notification
    notify-send -u low "Display" "Refresh rate: ${NEW_RATE}Hz" 2>/dev/null || true
else
    echo "Error: Failed to set ${NEW_RATE}Hz on $MONITOR" >&2
    exit 1
fi
