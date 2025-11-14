#!/bin/bash

# Get player status (prioritize Spotify > browsers > others)
player_status=$(playerctl -a status 2>/dev/null | head -n1)

if [ -z "$player_status" ]; then
    echo " No player"
    exit 0
fi

# Get active player
player=$(playerctl -l 2>/dev/null | head -n1)

# Get metadata
artist=$(playerctl metadata artist 2>/dev/null)
title=$(playerctl metadata title 2>/dev/null)

if [ -z "$artist" ] || [ -z "$title" ]; then
    echo " No media"
    exit 0
fi

# Truncate if too long
max_length=60
output="$artist - $title"
if [ ${#output} -gt $max_length ]; then
    output="${output:0:$max_length}..."
fi

# Icon based on player
if [[ "$player" == *"spotify"* ]]; then
    icon=""
elif [[ "$player" == *"firefox"* ]] || [[ "$player" == *"chrome"* ]]; then
    icon=""
else
    icon="ﱘ"
fi

# Show play/pause status
if [ "$player_status" = "Playing" ]; then
    echo "$icon $output"
else
    echo "$icon $output "
fi
