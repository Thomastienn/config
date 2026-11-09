#!/usr/bin/env bash
# Claude Code Stop hook: desktop notification with the project name and a short reply preview.
input=$(cat)
project=$(jq -r '.cwd // empty' <<<"$input")
# Pango markup is on in dunst, so escape the reply and drop Markdown symbols.
preview=$(jq -r '.last_assistant_message // empty
  | gsub("[`*#]"; "") | gsub("\\s+"; " ") | .[0:140]
  | gsub("&"; "&amp;") | gsub("<"; "&lt;") | gsub(">"; "&gt;")' <<<"$input")
notify-send -a 'Claude Code' -i "$HOME/thomas_config/claude/icon.svg" \
  "${project##*/}" "${preview:-Ready for you}"
