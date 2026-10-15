# Loaded after ble.sh; hooks leave the command's exit status intact.
desktop_command_begin() {
    _desktop_command_started=$SECONDS
    _desktop_command_text=$1
}

desktop_command_end() {
    local command_status=$? elapsed=$((SECONDS - ${_desktop_command_started:-SECONDS}))
    if ((elapsed >= 30 && command_status != 130)); then
        {
            printf '%s' "$_desktop_command_text" |
                /usr/bin/python3 "$HOME/thomas_config/scripts/command-finished.py" \
                    "$command_status" "$elapsed" "$$" >/dev/null 2>&1 &
            disown "$!" 2>/dev/null || :
        } 2>/dev/null
    fi
    return "$command_status"
}

blehook PREEXEC-=desktop_command_begin
blehook POSTEXEC-=desktop_command_end
blehook PREEXEC+=desktop_command_begin
blehook POSTEXEC+=desktop_command_end
