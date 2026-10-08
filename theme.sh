#!/bin/bash
# ================================================================
# CENTRALIZED THEME CONFIGURATION
# ================================================================
# Shell and Conky palette, coordinated with the native app configs.
# Current theme: Cozy Mint
# ================================================================

# Truecolor shell accents
export THEME_COLOR1="\033[38;2;167;204;174m"  # Mint (#A7CCAE)
export THEME_COLOR2="\033[38;2;238;232;220m"  # Cream (#EEE8DC)
export THEME_COLOR3="\033[38;2;192;175;213m"  # Lavender (#C0AFD5)
export THEME_COLOR4="\033[38;2;167;204;174m"  # Mint (#A7CCAE)
export THEME_COLOR5="\033[38;2;219;160;170m"  # Rose (#DBA0AA)
export THEME_COLOR6="\033[38;2;192;175;213m"  # Lavender (#C0AFD5)

# Standard colors
export THEME_GRAY="\033[38;2;171;175;164m"
export THEME_RESET="\033[00m"
export THEME_BOLD="\033[1m"

# Tmux Colors (color names for tmux)
export TMUX_COLOR_PRIMARY="#A7CCAE"
export TMUX_COLOR_ACCENT="#C0AFD5"
export TMUX_COLOR_SECONDARY="#272C27"
export TMUX_COLOR_TERTIARY="#DEC28A"
export TMUX_COLOR_HIGHLIGHT="#A7CCAE"

# Conky Colors (hex for conky - optimized for transparent bg)
export CONKY_COLOR1="A7CCAE"    # Mint headings
export CONKY_COLOR2="EEE8DC"    # Cream values
export CONKY_COLOR3="ABAFA4"    # Muted labels
export CONKY_COLOR4="5D6D5E"    # Sage separators
export CONKY_GRAPH1="A7CCAE"
export CONKY_GRAPH2="C0AFD5"
