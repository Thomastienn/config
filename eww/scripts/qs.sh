#!/usr/bin/env bash
# Quick-settings flyout backend: status JSON for eww, plus the actions its buttons run.
# Actions reuse the Polybar/i3 scripts so the bar and flyout never disagree.

DIR=$(dirname "$(readlink -f "$0")")
# Polybar/i3 don't read bashrc, so eww's build dir may not be on PATH.
EWW=("$(command -v eww || echo "$HOME/eww/target/release/eww")" -c "$DIR/..")
PB=$HOME/thomas_config/polybar/shapes/scripts
source "$HOME/thomas_config/scripts/backlight.sh"

# Do not let the daemon inherit the lock held by its launcher.
eww_cmd() { timeout -k 1s 3s "${EWW[@]}" "$@" 9>&-; }

case $1 in
    toggle|controls|close|wifi|timer|updates)
        exec 9>"${XDG_RUNTIME_DIR:-/run/user/$UID}/thomas-eww.lock" || exit 1
        flock -x 9 || exit 1 ;;
esac

json_str() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
num() { [[ $1 =~ ^[0-9]+$ ]] && echo "$1" || echo 0; }

panel_height() {
    local height screen_height
    # Use cached monitor state; probing outputs can stall the first open.
    height=$(timeout -k 1s 2s xrandr --current --listmonitors 2>/dev/null | awk 'NR == 2 { split($3, size, "x"); split(size[2], pixels, "/"); print pixels[1] }')
    [[ $height =~ ^[0-9]+$ ]] || height=1080
    screen_height=$(timeout -k 1s 2s xrandr --current 2>/dev/null | awk '/^Screen / { for (i=1; i<=NF; i++) if ($i == "current") { gsub(/,/, "", $(i+3)); print $(i+3); exit } }')
    if [[ $screen_height =~ ^[0-9]+$ ]] && ((screen_height < height)); then height=$screen_height; fi
    height=$((height - 104))
    ((height > ${1:-780})) && height=${1:-780}
    printf '%spx\n' "$height"
}

raise_flyout() {
    local window
    window=$(timeout -k 1s 2s xdotool search --sync --onlyvisible --name '^Eww - flyout$' | head -1)
    [[ $window ]] || return 1
    xdotool windowraise "$window" && xdotool windowfocus "$window"
}

status() {
    local vol vol_muted mic_muted bright engine kbd hz wifi gpu media playing battery
    vol=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oP '\d+(?=%)' | head -1)
    pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q yes && vol_muted=true || vol_muted=false
    pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -q yes && mic_muted=true || mic_muted=false
    bright=$("${backlight[@]}" -m 2>/dev/null | cut -d, -f4 | tr -d %)
    engine=$(ibus engine 2>/dev/null)
    case $engine in Unikey) kbd=VI ;; *us*) kbd=US ;; "") kbd=-- ;; *) kbd=${engine##*:} ;; esac
    hz=$(xrandr --current 2>/dev/null | grep -oP '\d+(?=\.\d+\*)' | head -1)
    wifi=$(nmcli -t -f active,ssid dev wifi list --rescan no 2>/dev/null | awk -F: '$1 == "yes" {print $2; exit}')
    gpu=$(prime-select query 2>/dev/null)
    media=$(playerctl metadata --format '{{artist}} - {{title}}' 2>/dev/null)
    [ "$media" = " - " ] && media=
    [ "$(playerctl status 2>/dev/null)" = Playing ] && playing=true || playing=false
    battery=$(/usr/bin/python3 "$HOME/thomas_config/scripts/battery-mode.py" status 2>/dev/null) ||
        battery='{"enabled":false,"available":false,"detail":"Unavailable","issues":[]}'
    printf '{"vol":%s,"vol_muted":%s,"mic_muted":%s,"bright":%s,"kbd":%s,"hz":%s,"wifi":%s,"gpu":%s,"media":%s,"playing":%s,"battery":%s}\n' \
        "$(num "$vol")" "$vol_muted" "$mic_muted" "$(num "$bright")" "$(json_str "$kbd")" "$(num "$hz")" \
        "$(json_str "$wifi")" "$(json_str "${gpu^}")" "$(json_str "$media")" "$playing" "$battery"
}

close() {
    local window
    eww_cmd close-all || return
    # The unmanaged panel borrows keyboard focus from i3's selected window.
    window=$(i3-msg -t get_tree | jq -r '.. | objects | select(.focused == true) | .window // empty') || return
    # i3's focus command is a no-op when that container is already selected.
    if [[ $window ]]; then
        timeout -k 1s 2s xdotool windowfocus --sync "$window"
    fi
}

case $1 in
    status) status ;;
    toggle|controls)
        # Start immediately: client commands otherwise each retry a missing daemon for a second.
        eww_cmd daemon >/dev/null 2>&1 || exit 1
        active=$(eww_cmd active-windows) || exit 1
        if grep -q '^flyout:' <<< "$active"; then
            if [[ $1 == controls ]]; then eww_cmd update qs_page=0; else close; fi
        else
            close || exit 1
            height=$(panel_height)
            # Roll back both windows if opening is interrupted or any step fails.
            trap close EXIT
            trap 'exit 1' HUP INT TERM
            eww_cmd update qs_page=0 && eww_cmd open closer &&
                eww_cmd open flyout --arg panel_height="$height" &&
                raise_flyout || exit 1
            trap - EXIT HUP INT TERM
        fi ;;
    page) [[ $2 =~ ^[0-3]$ ]] || exit 2; eww_cmd update qs_page="$2" ;;
    close) close ;;
    mic) pactl set-source-mute @DEFAULT_SOURCE@ toggle; polybar-msg action microphone hook 0 >/dev/null 2>&1 ;;
    kbd) "$PB/keyboard-switch.sh" >/dev/null 2>&1 ;;
    hz) "$PB/toggle-refresh-rate.sh" >/dev/null 2>&1 ;;
    battery) /usr/bin/python3 "$HOME/thomas_config/scripts/battery-mode.py" toggle >/dev/null ;;
    wifi) close; setsid -f kitty -e nmtui >/dev/null 2>&1 9>&- ;;
    timer) close; setsid -f /usr/bin/python3 "$HOME/thomas_config/scripts/polybar-timer.py" menu >/dev/null 2>&1 9>&- ;;
    apps-search) setsid -f /usr/bin/python3 "$HOME/thomas_config/scripts/desktop-controls.py" pick-app >/dev/null 2>&1 ;;
    updates) close; setsid -f exo-open --launch TerminalEmulator >/dev/null 2>&1 9>&- ;;
    vol) pactl set-sink-volume @DEFAULT_SINK@ "$(num "${2%.*}")%" ;;
    mute) pactl set-sink-mute @DEFAULT_SINK@ toggle ;;
    # Floor at 5% so a stray drag can't black out the panel.
    bright) b=$(num "${2%.*}"); "${backlight[@]}" -q s "$(( b < 5 ? 5 : b ))%" ;;
    prev|next) playerctl "$1" ;;
    play) playerctl play-pause ;;
    *) echo "usage: $0 status|toggle|controls|close|page N|mic|kbd|hz|battery|wifi|timer|apps-search|updates|vol N|mute|bright N|prev|play|next" >&2; exit 1 ;;
esac
