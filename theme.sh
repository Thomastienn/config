#!/bin/bash
# Load generated exports; a checkout remains usable before setup has run.
if [[ -r $HOME/thomas_config/themes/.generated/shell.sh ]]; then
    source "$HOME/thomas_config/themes/.generated/shell.sh"
else
    source <(/usr/bin/python3 "$HOME/thomas_config/scripts/theme.py" shell)
fi
