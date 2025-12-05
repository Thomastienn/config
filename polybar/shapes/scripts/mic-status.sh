#!/usr/bin/env bash

# Get mic mute status
icon=""
icon_muted=""
if pactl get-source-mute @DEFAULT_SOURCE@ | grep -q 'yes'; then
    echo "$icon_muted Muted"
else
    echo "$icon On"
fi
