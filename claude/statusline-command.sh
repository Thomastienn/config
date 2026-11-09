#!/bin/bash
# Status line (desktop theme, Nerd Font pills):
#   model · token budget · folder · git branch and diff · cost and time · 5h and weekly usage
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Follow the active desktop theme; fall back to Cozy Mint before the first theme render.
palette=$(jq -r '.colors | [.background, .surface, .text, .muted, .secondary, .primary, .warning, .error] | join(" ")' \
  "$HOME/thomas_config/themes/.generated/palette.json" 2>/dev/null)
read -r c_bg c_surface c_text c_muted c_lav c_mint c_sand c_rose \
  <<<"${palette:-#191B19 #272C27 #EEE8DC #ABAFA4 #C0AFD5 #A7CCAE #DEC28A #DBA0AA}"
rgb() { printf '%d;%d;%d' "0x${1:1:2}" "0x${1:3:2}" "0x${1:5:2}"; }
fg() { printf '\033[38;2;%sm' "$(rgb "$1")"; }
bg() { printf '\033[48;2;%sm' "$(rgb "$1")"; }
reset=$'\033[0m'
bold=$'\033[1m'
left=$'\ue0b6' right=$'\ue0b4'
# Nerd Font icons: folder, git branch, dollar, clock.
i_dir=$'\uf07c' i_git=$'\ue0a0' i_cost=$'\uf155' i_time=$'\uf017'

case "$cwd" in "$HOME"|"$HOME"/*) disp="~${cwd#"$HOME"}" ;; *) disp="$cwd" ;; esac

branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
dirty=""
if [ -n "$branch" ]; then
  [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null | head -n1)" ] && dirty=" ●"
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

# Percent colour: mint below 70, sand to 90, rose above.
level() { if [ "$1" -ge 90 ]; then echo "$c_rose"; elif [ "$1" -ge 70 ]; then echo "$c_sand"; else echo "$c_mint"; fi; }

out=""
# Bright pill: dark text on an accent colour.
pill() { out+="$(fg "$1")$left$(bg "$1")$(fg "$c_bg")$bold $2 $reset$(fg "$1")$right$reset "; }
# Quiet pill: coloured text on the surface colour.
soft() { out+="$(fg "$c_surface")$left$(bg "$c_surface")$1 $reset$(fg "$c_surface")$right$reset "; }

m="✻ $model"
[ -n "$effort" ] && m="$m $effort"
[ -n "$model" ] && pill "$c_lav" "$m"

if [ -n "$used" ]; then
  # Per-conversation token budget, not the model window: mint below 100k, sand to 150k, rose beyond.
  budget=150000
  if [ "$used" -ge "$budget" ]; then colour=$c_rose; elif [ "$used" -ge 100000 ]; then colour=$c_sand; else colour=$c_mint; fi
  filled=$(( used * 8 / budget )); [ "$filled" -gt 8 ] && filled=8
  bar=""; for i in 1 2 3 4 5 6 7 8; do if [ "$i" -le "$filled" ]; then bar+="█"; else bar+="░"; fi; done
  tok="$(fmt_tok "$used")"
  [ -n "$size" ] && tok="$tok/$(fmt_tok "$size")"
  pill "$colour" "󰍛 $bar $tok"
fi

soft "$(fg "$c_text") $i_dir $disp"
if [ -n "$branch" ]; then
  git_info="$(fg "$c_mint") $i_git $branch$(fg "$c_sand")$dirty"
  [ "$added$removed" != "00" ] && git_info+="  $(fg "$c_mint")+$added $(fg "$c_rose")-$removed"
  soft "$git_info"
fi

session=""
[ -n "$cost" ] && session+="$(fg "$c_sand") $i_cost $(printf '%.2f' "$cost")"
if [ -n "$ms" ]; then
  mins=$(( ms / 60000 ))
  if [ "$mins" -ge 60 ]; then t="$((mins / 60))h$(printf '%02d' $((mins % 60)))m"; else t="${mins}m"; fi
  session+="  $(fg "$c_muted")$i_time $t"
fi
[ -n "$session" ] && soft "$session"

# Usage limits with reset times: 5h as a clock time, weekly as day and time.
if [ -n "$five" ]; then
  text="󰔟 5h ${five}%"
  [ -n "$five_reset" ] && text+=" ↻$(date -d "@$five_reset" +%H:%M)"
  pill "$(level "$five")" "$text"
fi
if [ -n "$week" ]; then
  text="󰃭 7d ${week}%"
  [ -n "$week_reset" ] && text+=" ↻$(date -d "@$week_reset" '+%a %H:%M')"
  pill "$(level "$week")" "$text"
fi

printf '%s\n' "${out% }"
