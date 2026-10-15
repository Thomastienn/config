#!/bin/bash
# Brightness control script for i3

source "$(dirname "$(readlink -f "$0")")/backlight.sh"

case "$1" in
    up)
        "${backlight[@]}" s +5%
        VALUE=$("${backlight[@]}" -m | cut -d, -f4 | tr -d %)
        notify-send -t 1000 -a "brightness" -h "int:value:$VALUE" -r 1113 "Brightness Up"
        ;;
    down)
        "${backlight[@]}" s 5%-
        VALUE=$("${backlight[@]}" -m | cut -d, -f4 | tr -d %)
        notify-send -t 1000 -a "brightness" -h "int:value:$VALUE" -r 1113 "Brightness Down"
        ;;
    *)
        echo "Usage: $0 {up|down}"
        exit 1
        ;;
esac
