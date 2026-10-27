#!/usr/bin/env bash
source "$HOME/thomas_config/theme.sh"

# Get mic mute status with error handling

icon="%{F${THEME_PRIMARY}}%{F-}"
icon_muted="%{F${THEME_ERROR}}%{F-}"

status=$(pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null) || {
    echo "$icon --"
    setsid -f "$(dirname "$0")/retry-hook.sh" microphone pactl get-source-mute @DEFAULT_SOURCE@ >/dev/null 2>&1
    exit 0
}

if echo "$status" | grep -q 'yes'; then
    echo "$icon_muted"
else
    echo "$icon"
fi
