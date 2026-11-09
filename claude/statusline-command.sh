#!/bin/bash
# Status line (Claude-orange palette, Nerd Font icons, │ separators):
#   model · token budget · folder · git branch and diff · cost and time · 5h and weekly usage
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Fixed warm analogous palette around Claude's orange; light-to-hot ramp for levels.
c_line=#6E5648 c_text=#F3E6DA c_muted=#B39C8B
c_claude=#D97757 c_peach=#F2B091 c_gold=#E8BE78 c_hot=#E5534B
rgb() { printf '%d;%d;%d' "0x${1:1:2}" "0x${1:3:2}" "0x${1:5:2}"; }
fg() { printf '\033[38;2;%sm' "$(rgb "$1")"; }
reset=$'\033[0m'
bold=$'\033[1m'
# Nerd Font icons: folder, git branch, dollar, clock, memory, hourglass, calendar, refresh.
i_dir=$'\uf07c' i_git=$'\ue0a0' i_cost=$'\uf155' i_time=$'\uf017'
i_ctx=$'\U000f035b' i_five=$'\U000f051f' i_week=$'\U000f00ed' i_reset=$'\uf021'

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

# Percent colour: gold below 70, orange to 90, red above.
level() { if [ "$1" -ge 90 ]; then echo "$c_hot"; elif [ "$1" -ge 70 ]; then echo "$c_claude"; else echo "$c_gold"; fi; }

out=""
# Model: bold accent text.
pill() { out+="$(fg "$1")$bold$2$reset$(fg "$c_line")  │  $reset"; }
# Section in bright text; callers colour icons and numbers.
soft() { out+="$(fg "$c_text")$1$reset$(fg "$c_line")  │  $reset"; }
# Coloured fragment inside a section, back to bright text afterwards.
hue() { printf '%s%s%s' "$(fg "$1")" "$2" "$(fg "$c_text")"; }

m="✻ $model"
[ -n "$effort" ] && m="$m $effort"
[ -n "$model" ] && pill "$c_claude" "$m"

if [ -n "$used" ]; then
  # Per-conversation token budget, not the model window: gold below 100k, orange to 150k, red beyond.
  budget=150000
  if [ "$used" -ge "$budget" ]; then colour=$c_hot; elif [ "$used" -ge 100000 ]; then colour=$c_claude; else colour=$c_gold; fi
  filled=$(( used * 10 / budget )); [ "$filled" -gt 10 ] && filled=10
  full=""; empty=""
  for i in 1 2 3 4 5 6 7 8 9 10; do if [ "$i" -le "$filled" ]; then full+="━"; else empty+="━"; fi; done
  tok="$bold$(fmt_tok "$used")$reset$(fg "$c_muted")"
  [ -n "$size" ] && tok+="/$(fmt_tok "$size")"
  soft "$(hue "$colour" "$i_ctx $full")$(hue "$c_line" "$empty") $(hue "$colour" "$tok")"
fi

soft "$(hue "$c_peach" "$i_dir")  $disp"
if [ -n "$branch" ]; then
  git_info="$(hue "$c_claude" "$i_git") $branch$(hue "$c_gold" "$dirty")"
  [ "$added$removed" != "00" ] && git_info+="  $(hue "$c_gold" "+$added") $(hue "$c_hot" "-$removed")"
  soft "$git_info"
fi

session=""
[ -n "$cost" ] && session+="$(hue "$c_gold" "$i_cost") $(printf '%.2f' "$cost")"
if [ -n "$ms" ]; then
  mins=$(( ms / 60000 ))
  if [ "$mins" -ge 60 ]; then t="$((mins / 60))h$(printf '%02d' $((mins % 60)))m"; else t="${mins}m"; fi
  session+="  $(hue "$c_peach" "$i_time")  $t"
fi
[ -n "$session" ] && soft "$session"

# Usage limits with reset times: 5h as a clock time, weekly as day and time.
limits=""
if [ -n "$five" ]; then
  limits+="$(hue "$(level "$five")" "$i_five") 5h $(hue "$(level "$five")" "$bold${five}%$reset")"
  [ -n "$five_reset" ] && limits+=" $(hue "$c_muted" "$i_reset $(date -d "@$five_reset" +%H:%M)")"
fi
if [ -n "$week" ]; then
  [ -n "$limits" ] && limits+="   "
  limits+="$(hue "$(level "$week")" "$i_week") 7d $(hue "$(level "$week")" "$bold${week}%$reset")"
  [ -n "$week_reset" ] && limits+=" $(hue "$c_muted" "$i_reset $(date -d "@$week_reset" '+%a %H:%M')")"
fi
[ -n "$limits" ] && soft "$limits"

printf '%s\n' "${out%  │  *}"
