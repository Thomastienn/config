#!/usr/bin/env bash

# Get mic mute status with error handling

icon="%{F#A7CCAE}%{F-}"
icon_muted="%{F#DBA0AA}%{F-}"

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
