#!/usr/bin/env bash

# Updates check with error handling and timeout

get_updates() {
    local mint_updates=0
    local flatpak_updates=0
    
    # Refresh and check mintUpdate cache
    if command -v mintupdate-cli &>/dev/null; then
        timeout 30 mintupdate-cli check &>/dev/null
        if [ -f /var/lib/linuxmint/mintUpdate/updates.list ]; then
            mint_updates=$(wc -l < /var/lib/linuxmint/mintUpdate/updates.list 2>/dev/null) || mint_updates=0
        fi
    fi
    
    # Check Flatpak updates
    if command -v flatpak &>/dev/null; then
        flatpak_updates=$(timeout 10 flatpak remote-ls --updates 2>/dev/null | wc -l) || flatpak_updates=0
    fi
    
    echo $((mint_updates + flatpak_updates))
}

UPDATES=$(get_updates)

# Ensure valid number
[[ ! "$UPDATES" =~ ^[0-9]+$ ]] && UPDATES=0

if (( UPDATES == 0 )); then
    echo " None"
elif (( UPDATES == 1 )); then
    echo " $UPDATES"
else
    echo " $UPDATES"
fi
