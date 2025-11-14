#!/usr/bin/env bash

# Toggle between keyboard layouts
current=$(setxkbmap -query | grep layout | awk '{print $2}')

if [[ $current == "us" ]]; then
    setxkbmap -layout vn
else
    setxkbmap -layout us
fi
