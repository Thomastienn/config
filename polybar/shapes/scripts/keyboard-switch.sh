#!/usr/bin/env bash

# Get current IBus engine
current=$(ibus engine)

# Switch between US and Unikey
if [[ $current == "Unikey" ]]; then
    ibus engine xkb:us::eng
else
    ibus engine Unikey
fi

# Trigger Polybar update
polybar-msg hook keyboard 1
