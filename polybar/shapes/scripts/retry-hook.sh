#!/usr/bin/env bash
# Re-run a Polybar ipc hook once its backing service answers.
# At login Polybar can start before ibus/pipewire, so the first hook prints "--".
# Usage: retry-hook.sh <module> <check command...>

module=$1
shift

# ponytail: 30 tries x 2s, then wait for the next click or hook.
for _ in {1..30}; do
    sleep 2
    "$@" >/dev/null 2>&1 && exec polybar-msg action "$module" hook 0
done
