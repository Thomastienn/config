#!/bin/bash
# ================================================================
# CENTRALIZED THEME CONFIGURATION
# ================================================================
# Change these colors to switch the entire theme across all tools
# Current theme: Sky Blue
# ================================================================

# Sky Blue Theme Colors (ANSI/Terminal)
export THEME_COLOR1="\033[38;5;117m"    # Light sky blue
export THEME_COLOR2="\033[38;5;75m"     # Sky blue
export THEME_COLOR3="\033[38;5;111m"    # Medium sky blue
export THEME_COLOR4="\033[38;5;39m"     # Bright sky blue
export THEME_COLOR5="\033[38;5;81m"     # Cyan blue
export THEME_COLOR6="\033[38;5;123m"    # Pale sky blue

# Standard colors
export THEME_GRAY="\033[38;5;240m"
export THEME_RESET="\033[00m"
export THEME_BOLD="\033[1m"

# Tmux Colors (color names for tmux)
export TMUX_COLOR_PRIMARY="colour75"         # Sky blue for primary elements
export TMUX_COLOR_ACCENT="colour39"          # Bright sky blue for accents
export TMUX_COLOR_SECONDARY="colour117"      # Light sky blue for secondary
export TMUX_COLOR_TERTIARY="colour111"       # Medium sky blue
export TMUX_COLOR_HIGHLIGHT="colour81"       # Cyan blue for highlights

# Conky Colors (hex for conky)
export CONKY_COLOR1="4FC3F7"    # Light sky blue
export CONKY_COLOR2="FFFFFF"    # White
export CONKY_COLOR3="AAAAAA"    # Gray
export CONKY_COLOR4="29B6F6"    # Medium sky blue
export CONKY_GRAPH1="4FC3F7"    # Graph color 1 (light sky blue)
export CONKY_GRAPH2="29B6F6"    # Graph color 2 (medium sky blue)
