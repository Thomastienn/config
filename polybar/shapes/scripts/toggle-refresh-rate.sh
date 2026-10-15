#!/bin/bash

# Get primary monitor
MONITOR=$(xrandr --current | grep " connected primary" | awk '{print $1}')
MONITOR=${MONITOR:-$(xrandr --current | grep " connected" | head -n1 | awk '{print $1}')}

# Keep the active resolution and use only rates offered by this display.
MODE=$(xrandr --current | awk -v monitor="$MONITOR" '
    /^[^ ]/ { active = ($1 == monitor) }
    active && /\*/ { print; exit }')
read -r RESOLUTION RATES <<< "$MODE"
AVAILABLE=$(printf '%s\n' "$RATES" | tr ' ' '\n' | tr -d '*+' | sed '/^$/d' | sort -n)
RATE_HIGH=$(printf '%s\n' "$AVAILABLE" | tail -1)
# Prefer 60 Hz when supported; otherwise use the lowest available rate.
RATE_LOW=$(printf '%s\n' "$AVAILABLE" | awk '$1 >= 59 && $1 <= 61 { print; exit }')
RATE_LOW=${RATE_LOW:-$(printf '%s\n' "$AVAILABLE" | head -1)}

# Get current refresh rate
CURRENT=$(printf '%s\n' "$MODE" | grep -oP '\d+\.\d+(?=\*)')

if [[ -z "$CURRENT" ]]; then
    echo "Error: Monitor $MONITOR not found or not connected" >&2
    exit 1
fi

# Toggle logic
if awk -v current="$CURRENT" -v high="$RATE_HIGH" 'BEGIN { exit !(current >= high - 0.5) }'; then
    NEW_RATE="$RATE_LOW"
else
    NEW_RATE="$RATE_HIGH"
fi

# Apply change
if xrandr --output "$MONITOR" --mode "$RESOLUTION" --rate "$NEW_RATE" 2>/dev/null; then
    echo "Switched $MONITOR to ${NEW_RATE}Hz"
    
    # Notify polybar (if running)
    "$HOME/thomas_config/polybar/shapes/scripts/get-refresh-rate.sh"
    
    # Optional: Send desktop notification
    notify-send -u low "Display" "Refresh rate: ${NEW_RATE}Hz" 2>/dev/null || true
else
    echo "Error: Failed to set ${NEW_RATE}Hz on $MONITOR" >&2
    exit 1
fi
