#!/usr/bin/env bash

# Get current layout
current=$(setxkbmap -query | grep layout | awk '{print $2}')

# Switch to the other layout (NO alt+shift option)
if [[ $current == *"vn"* ]]; then
    setxkbmap us
else
    setxkbmap vn
fi

# Trigger Polybar update
polybar-msg hook keyboard 1
