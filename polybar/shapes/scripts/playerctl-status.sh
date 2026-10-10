#!/bin/bash

icon_mute="%{F#ABAFA4}󰖁%{F-}"

# Function to get and display status
get_status() {
    # Get player status (prioritize Spotify > browsers > others)
    player_status=$(playerctl -a status 2>/dev/null | head -n1)

    if [ -z "$player_status" ]; then
        echo "$icon_mute"
        return
    fi

    # Get active player
    player=$(playerctl -l 2>/dev/null | head -n1)

    # Get metadata
    artist=$(playerctl metadata artist 2>/dev/null)
    title=$(playerctl metadata title 2>/dev/null)

    if [ -z "$artist" ] || [ -z "$title" ]; then
        echo "$icon_mute"
        return
    fi

    # Icon based on player
    if [[ "$player" == *"spotify"* ]]; then
        icon=""
    elif [[ "$player" == *"firefox"* ]] || [[ "$player" == *"chrome"* ]]; then
        icon=""
    else
        icon="%{F#A7CCAE}%{F-}"
    fi
    icon="%{F#A7CCAE}%{F-}"

    # Show play/pause status
    if [ "$player_status" = "Playing" ]; then
        echo "$icon"
    else
        echo "$icon_mute"
    fi
}

# Output initial state
get_status

# Follow playerctl events - updates ONLY when something changes!
playerctl status --follow 2>/dev/null | while read -r status; do
    get_status
done
