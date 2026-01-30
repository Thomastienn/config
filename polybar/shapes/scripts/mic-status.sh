#!/usr/bin/env bash

# Get mic mute status with error handling

icon=""
icon_muted=""

status=$(pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null) || {
    echo "$icon --"
    exit 0
}

if echo "$status" | grep -q 'yes'; then
    echo "$icon_muted Muted"
else
    echo "$icon On"
fi
