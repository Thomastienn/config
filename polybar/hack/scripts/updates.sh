#!/usr/bin/env bash

get_updates() {
    local mint_updates=0
    local flatpak_updates=0
    
    # Refresh and check mintUpdate cache
    if command -v mintupdate-cli &>/dev/null; then
        mintupdate-cli check &>/dev/null
        if [ -f /var/lib/linuxmint/mintUpdate/updates.list ]; then
            mint_updates=$(wc -l < /var/lib/linuxmint/mintUpdate/updates.list)
        fi
    fi
    
    # Check Flatpak updates
    if command -v flatpak &>/dev/null; then
        flatpak_updates=$(flatpak remote-ls --updates 2>/dev/null | wc -l)
    fi
    
    echo $((mint_updates + flatpak_updates))
}

# Run once and exit
UPDATES=$(get_updates)

if (( UPDATES == 0 )); then
    echo " None"
elif (( UPDATES == 1 )); then
    echo " $UPDATES"
else
    echo " $UPDATES"
fi
