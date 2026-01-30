#!/usr/bin/env bash

# Keyboard layout display with error handling

engine=$(ibus engine 2>/dev/null) || engine=""

if [[ -z "$engine" ]]; then
    echo " --"
    exit 0
fi

case $engine in
    Unikey)
        echo "  Unikey"
        ;;
    *us*)
        echo "  US"
        ;;
    *)
        echo "  ${engine##*:}"
        ;;
esac
