#!/bin/bash
# ================================================================
# CENTRALIZED THEME CONFIGURATION
# ================================================================
# Change these colors to switch the entire theme across all tools
# Current theme: Tree (Forest Green & Earth Brown)
# ================================================================

# Tree Theme Colors (ANSI/Terminal)
export THEME_COLOR1="\033[38;5;108m"    # Soft sage green
export THEME_COLOR2="\033[38;5;72m"     # Medium forest green
export THEME_COLOR3="\033[38;5;107m"    # Pale olive green
export THEME_COLOR4="\033[38;5;114m"    # Light spring green
export THEME_COLOR5="\033[38;5;65m"     # Muted forest green
export THEME_COLOR6="\033[38;5;137m"    # Warm tan/brown

# Standard colors
export THEME_GRAY="\033[38;5;240m"
export THEME_RESET="\033[00m"
export THEME_BOLD="\033[1m"

# Tmux Colors (color names for tmux)
export TMUX_COLOR_PRIMARY="colour108"        # Soft sage green for primary
export TMUX_COLOR_ACCENT="colour114"         # Light spring green for accents
export TMUX_COLOR_SECONDARY="colour72"       # Medium forest green
export TMUX_COLOR_TERTIARY="colour137"       # Tan/brown for contrast
export TMUX_COLOR_HIGHLIGHT="colour107"      # Pale olive for highlights

# Conky Colors (hex for conky)
export CONKY_COLOR1="87AF87"    # Soft sage green
export CONKY_COLOR2="FFFFFF"    # White
export CONKY_COLOR3="AAAAAA"    # Gray
export CONKY_COLOR4="5F8700"    # Deep forest green
export CONKY_GRAPH1="87AF87"    # Graph color 1 (soft sage)
export CONKY_GRAPH2="5FAF5F"    # Graph color 2 (medium green)
