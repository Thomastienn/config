#!/usr/bin/env bash
# Names and numeric IDs vary across machines and boots.
xinput list --name-only | while IFS= read -r device; do
    case "$device" in
        *[Tt]ouchpad*) xinput set-prop "$device" "libinput Natural Scrolling Enabled" 1 ;;
    esac
done
