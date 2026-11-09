#!/bin/bash
# Status line (Cozy Mint theme): model effort · budget bar tokens · cwd · branch · lines · cost · time · limits
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Follow the active desktop theme; fall back to Cozy Mint before the first theme render.
palette=$(jq -r '.colors | [.muted, .separator, .secondary, .primary, .warning, .error] | join(" ")' \
  "$HOME/thomas_config/themes/.generated/palette.json" 2>/dev/null)
read -r c_gray c_dim c_lav c_mint c_sand c_rose <<<"${palette:-#ABAFA4 #5D6D5E #C0AFD5 #A7CCAE #DEC28A #DBA0AA}"
fg() { printf '\\033[38;2;%d;%d;%dm' "0x${1:1:2}" "0x${1:3:2}" "0x${1:5:2}"; }
gray=$(fg "$c_gray")
dim=$(fg "$c_dim")
lav="\\033[1m$(fg "$c_lav")"
mint=$(fg "$c_mint")
sand=$(fg "$c_sand")
rose=$(fg "$c_rose")
reset='\033[00m'

case "$cwd" in "$HOME"|"$HOME"/*) disp="~${cwd#"$HOME"}" ;; *) disp="$cwd" ;; esac

branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
dirty=""
if [ -n "$branch" ]; then
  [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null | head -n1)" ] && dirty="*"
fi

IFS=$'\x1f' read -r model effort used size added removed cost ms five five_reset week week_reset < <(echo "$input" | jq -r '[
  .model.display_name // "", .effort.level // "",
  (.context_window.total_input_tokens // ((.context_window.current_usage // empty) | (.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens)) // ""),
  .context_window.context_window_size // "",
  .cost.total_lines_added // 0, .cost.total_lines_removed // 0,
  .cost.total_cost_usd // "", .cost.total_duration_ms // "",
  (.rate_limits.five_hour.used_percentage // "" | if type == "number" then floor else . end), .rate_limits.five_hour.resets_at // "",
  (.rate_limits.seven_day.used_percentage // "" | if type == "number" then floor else . end), .rate_limits.seven_day.resets_at // ""] | map(tostring) | join("\u001f")')

# Compact number: 45213 -> 45.2k, 200000 -> 200k, 1000000 -> 1M
fmt_tok() {
  awk -v n="$1" 'BEGIN {
    if (n >= 1000000) { v = sprintf("%.1f", n/1000000); sub(/\.0$/, "", v); print v "M" }
    else if (n >= 1000) { v = sprintf("%.1f", n/1000); sub(/\.0$/, "", v); print v "k" }
    else print n
  }'
}

# Percent colour: calm below 70, sand to 90, rose above.
level() { if [ "$1" -ge 90 ]; then printf %s "$rose"; elif [ "$1" -ge 70 ]; then printf %s "$sand"; else printf %s "$gray"; fi; }

sep="${dim} · ${reset}"
out=""
add() { if [ -n "$out" ]; then out="${out}${sep}$1"; else out="$1"; fi; }

m="$model"
[ -n "$effort" ] && m="$m $effort"
[ -n "$m" ] && add "${lav}${m}${reset}"

if [ -n "$used" ]; then
  # Per-conversation token budget, not the model window: mint below 100k, sand to 150k, rose beyond.
  budget=150000
  if [ "$used" -ge "$budget" ]; then colour=$rose; elif [ "$used" -ge 100000 ]; then colour=$sand; else colour=$mint; fi
  filled=$(( used * 8 / budget )); [ "$filled" -gt 8 ] && filled=8
  bar=""; for i in 1 2 3 4 5 6 7 8; do if [ "$i" -le "$filled" ]; then bar="$bar▰"; else bar="$bar▱"; fi; done
  tok="$(fmt_tok "$used")"
  [ -n "$size" ] && tok="$tok${dim}/$(fmt_tok "$size")"
  add "${colour}${bar} ${tok}${reset}"
fi

add "${gray}${disp}${reset}"
[ -n "$branch" ] && add "${mint}${branch}${dirty}${reset}"
[ "$added$removed" != "00" ] && add "${mint}+${added}${reset} ${rose}-${removed}${reset}"
[ -n "$cost" ] && add "${gray}\$$(printf '%.2f' "$cost")${reset}"
if [ -n "$ms" ]; then
  mins=$(( ms / 60000 ))
  if [ "$mins" -ge 60 ]; then t="$((mins / 60))h$(printf '%02d' $((mins % 60)))m"; else t="${mins}m"; fi
  add "${gray}${t}${reset}"
fi
# Usage limits with reset times: 5h as a clock time, weekly as day and time.
if [ -n "$five" ]; then
  limit="$(level "$five")5h ${five}%"
  [ -n "$five_reset" ] && limit="$limit${dim} ↻$(date -d "@$five_reset" +%H:%M)"
  add "${limit}${reset}"
fi
if [ -n "$week" ]; then
  limit="$(level "$week")7d ${week}%"
  [ -n "$week_reset" ] && limit="$limit${dim} ↻$(date -d "@$week_reset" '+%a %H:%M')"
  add "${limit}${reset}"
fi

printf "%b\n" "$out"
