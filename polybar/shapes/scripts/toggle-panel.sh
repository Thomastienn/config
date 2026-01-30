#!/bin/bash
# Toggle secondary info panel visibility in polybar
# Uses polybar-msg to show/hide the panel-info module via IPC

STATE_FILE="/tmp/polybar-panel-state"

# Check current state
if [[ -f "$STATE_FILE" ]] && [[ "$(cat $STATE_FILE)" == "visible" ]]; then
    # Hide panel - set panel-info to hook 1 (empty), toggle icon to hook 1 (expand arrow)
    echo "hidden" > "$STATE_FILE"
    polybar-msg action panel-info hook 1
    polybar-msg action panel-toggle hook 1
else
    # Show panel - set panel-info to hook 0 (info), toggle icon to hook 0 (collapse arrow)
    echo "visible" > "$STATE_FILE"
    polybar-msg action panel-info hook 0
    polybar-msg action panel-toggle hook 0
fi
