#!/usr/bin/env bash
# Claude Code Stop/Notification hook: desktop notification with the project name and a short message.
input=$(cat)
project=$(jq -r '.cwd // empty' <<<"$input")
# Notification events carry .message (permission or question); Stop carries the reply.
# Pango markup is on in dunst, so escape the text and drop Markdown symbols.
preview=$(jq -r '.message // .last_assistant_message // empty
  | gsub("[`*#]"; "") | gsub("\\s+"; " ") | .[0:140]
  | gsub("&"; "&amp;") | gsub("<"; "&lt;") | gsub(">"; "&gt;")' <<<"$input")
urgency=normal
[ "$(jq -r '.hook_event_name // empty' <<<"$input")" = Notification ] && urgency=critical
notify-send -a 'Claude Code' -u "$urgency" -i "$HOME/thomas_config/claude/icon.svg" \
  "${project##*/}" "${preview:-Ready for you}"
