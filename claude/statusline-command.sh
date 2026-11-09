#!/bin/bash
# Status line (Cozy Mint theme): model effort · tokens · cwd · branch
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

gray='\033[38;2;171;175;164m'
lav='\033[1m\033[38;2;192;175;213m'
mint='\033[38;2;167;204;174m'
reset='\033[00m'

case "$cwd" in "$HOME"|"$HOME"/*) disp="~${cwd#"$HOME"}" ;; *) disp="$cwd" ;; esac

branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
dirty=""
if [ -n "$branch" ]; then
  [ -n "$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null | head -n1)" ] && dirty="*"
fi

model=$(echo "$input" | jq -r '.model.display_name // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
used=$(echo "$input" | jq -r '.context_window.total_input_tokens // ((.context_window.current_usage // empty) | (.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens)) // empty')
size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')

# Compact number: 45213 -> 45.2k, 200000 -> 200k, 1000000 -> 1M
fmt_tok() {
  awk -v n="$1" 'BEGIN {
    if (n >= 1000000) { v = sprintf("%.1f", n/1000000); sub(/\.0$/, "", v); print v "M" }
    else if (n >= 1000) { v = sprintf("%.1f", n/1000); sub(/\.0$/, "", v); print v "k" }
    else print n
  }'
}

# Codex-style: "model effort · used/size · ~/dir · branch*"
sep="${gray} · ${reset}"
out=""
add() { if [ -n "$out" ]; then out="${out}${sep}$1"; else out="$1"; fi; }

m="$model"
[ -n "$effort" ] && m="$m $effort"
[ -n "$m" ] && add "${lav}${m}${reset}"
if [ -n "$used" ]; then
  tok="$(fmt_tok "$used")"
  if [ -n "$size" ]; then tok="$tok/$(fmt_tok "$size")"; else tok="$tok tokens"; fi
  add "${gray}${tok}${reset}"
fi
add "${gray}${disp}${reset}"
[ -n "$branch" ] && add "${mint}${branch}${dirty}${reset}"

printf "%b\n" "$out"
