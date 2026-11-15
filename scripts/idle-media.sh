#!/bin/bash
# xidlehook's --not-when-audio/--not-when-fullscreen see open silent streams and paused
# fullscreen video as activity, so pause the idle countdown only while media plays.
# shortcut: MPRIS players only (browsers, Spotify, mpv-mpris); calls and games are not covered.
while sleep 30; do
    if playerctl -a status 2>/dev/null | grep -qx Playing; then
        "$HOME/.cargo/bin/xidlehook-client" --socket "$XDG_RUNTIME_DIR/thomas-xidlehook.sock" reset-idle >/dev/null 2>&1
    fi
done
