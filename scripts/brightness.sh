#!/bin/bash
# Brightness control script for i3

DEVICE="nvidia_wmi_ec_backlight"

case "$1" in
    up)
        brightnessctl --device="$DEVICE" s +5%
        VALUE=$(brightnessctl --device="$DEVICE" -m | cut -d, -f4 | tr -d %)
        notify-send -t 1000 -a "brightness" -h "int:value:$VALUE" -r 1113 "Brightness Up"
        ;;
    down)
        brightnessctl --device="$DEVICE" s 5%-
        VALUE=$(brightnessctl --device="$DEVICE" -m | cut -d, -f4 | tr -d %)
        notify-send -t 1000 -a "brightness" -h "int:value:$VALUE" -r 1113 "Brightness Down"
        ;;
    *)
        echo "Usage: $0 {up|down}"
        exit 1
        ;;
esac
