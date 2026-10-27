#!/usr/bin/env bash
source "$HOME/thomas_config/theme.sh"

# Keyboard layout display with error handling

engine=$(ibus engine 2>/dev/null) || engine=""

if [[ -z "$engine" ]]; then
    echo " --"
    setsid -f "$(dirname "$0")/retry-hook.sh" keyboard ibus engine >/dev/null 2>&1
    exit 0
fi

case $engine in
    Unikey)
        echo "%{F${THEME_SECONDARY}}VI%{F-}"
        ;;
    *us*)
        echo "US"
        ;;
    *)
        echo "${engine##*:}"
        ;;
esac
