#!/bin/bash
# ================================================================
# CENTRALIZED THEME CONFIGURATION
# ================================================================
# Change these colors to switch the entire theme across all tools
# Current theme: Obsidian Steel (Eye-Friendly Dark Professional)
# ================================================================

# Obsidian Steel Theme Colors (ANSI/Terminal)
export THEME_COLOR1="\033[38;5;67m"     # Steel blue (#6E8898)
export THEME_COLOR2="\033[38;5;60m"     # Gunmetal (#4A5568)
export THEME_COLOR3="\033[38;5;109m"    # Pale steel (#8FA3B0)
export THEME_COLOR4="\033[38;5;66m"     # Iron (#718096)
export THEME_COLOR5="\033[38;5;242m"    # Dim gray (#5C6370)
export THEME_COLOR6="\033[38;5;137m"    # Muted copper (#B87A5E)

# Standard colors
export THEME_GRAY="\033[38;5;243m"
export THEME_RESET="\033[00m"
export THEME_BOLD="\033[1m"

# Tmux Colors (color names for tmux)
export TMUX_COLOR_PRIMARY="colour67"         # Steel blue for primary
export TMUX_COLOR_ACCENT="colour109"         # Pale steel for accents
export TMUX_COLOR_SECONDARY="colour60"       # Gunmetal
export TMUX_COLOR_TERTIARY="colour137"       # Muted copper for contrast
export TMUX_COLOR_HIGHLIGHT="colour66"       # Iron for highlights

# Conky Colors (hex for conky - optimized for transparent bg)
export CONKY_COLOR1="6E8898"    # Steel blue (headers)
export CONKY_COLOR2="DDDDDD"    # Light gray (values)
export CONKY_COLOR3="888888"    # Medium gray (labels)
export CONKY_COLOR4="555555"    # Dark gray (muted)
export CONKY_GRAPH1="6E8898"    # Graph color 1 (steel blue)
export CONKY_GRAPH2="8FA3B0"    # Graph color 2 (pale steel)
