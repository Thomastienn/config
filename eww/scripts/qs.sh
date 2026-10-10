#!/usr/bin/env bash
# Quick-settings flyout backend: status JSON for eww, plus the actions its buttons run.
# Actions reuse the Polybar/i3 scripts so the bar and flyout never disagree.

DIR=$(dirname "$(readlink -f "$0")")
# Polybar/i3 don't read bashrc, so eww's build dir may not be on PATH.
EWW=("$(command -v eww || echo "$HOME/eww/target/release/eww")" -c "$DIR/..")
PB=$HOME/thomas_config/polybar/shapes/scripts
BACKLIGHT=nvidia_wmi_ec_backlight

json_str() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '"%s"' "$s"; }
num() { [[ $1 =~ ^[0-9]+$ ]] && echo "$1" || echo 0; }

status() {
    local vol vol_muted mic_muted bright engine kbd hz wifi gpu media playing
    vol=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oP '\d+(?=%)' | head -1)
    pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q yes && vol_muted=true || vol_muted=false
    pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -q yes && mic_muted=true || mic_muted=false
    bright=$(brightnessctl -d "$BACKLIGHT" -m 2>/dev/null | cut -d, -f4 | tr -d %)
    engine=$(ibus engine 2>/dev/null)
    case $engine in Unikey) kbd=VI ;; *us*) kbd=US ;; "") kbd=-- ;; *) kbd=${engine##*:} ;; esac
    hz=$(xrandr --current 2>/dev/null | grep -oP '\d+(?=\.\d+\*)' | head -1)
    wifi=$(nmcli -t -f active,ssid dev wifi list --rescan no 2>/dev/null | awk -F: '$1 == "yes" {print $2; exit}')
    gpu=$(prime-select query 2>/dev/null)
    media=$(playerctl metadata --format '{{artist}} - {{title}}' 2>/dev/null)
    [ "$media" = " - " ] && media=
    [ "$(playerctl status 2>/dev/null)" = Playing ] && playing=true || playing=false
    printf '{"vol":%s,"vol_muted":%s,"mic_muted":%s,"bright":%s,"kbd":%s,"hz":%s,"wifi":%s,"gpu":%s,"media":%s,"playing":%s}\n' \
        "$(num "$vol")" "$vol_muted" "$mic_muted" "$(num "$bright")" "$(json_str "$kbd")" "$(num "$hz")" \
        "$(json_str "$wifi")" "$(json_str "${gpu^}")" "$(json_str "$media")" "$playing"
}

close() { "${EWW[@]}" close flyout closer 2>/dev/null; }

case $1 in
    status) status ;;
    toggle)
        if "${EWW[@]}" active-windows 2>/dev/null | grep -q '^flyout'; then close
        else "${EWW[@]}" open closer && "${EWW[@]}" open flyout; fi ;;
    close) close ;;
    mic) pactl set-source-mute @DEFAULT_SOURCE@ toggle; polybar-msg action microphone hook 0 >/dev/null 2>&1 ;;
    kbd) "$PB/keyboard-switch.sh" >/dev/null 2>&1 ;;
    hz) "$PB/toggle-refresh-rate.sh" >/dev/null 2>&1 ;;
    wifi) close; setsid -f kitty -e nmtui >/dev/null 2>&1 ;;
    updates) close; setsid -f exo-open --launch TerminalEmulator >/dev/null 2>&1 ;;
    vol) pactl set-sink-volume @DEFAULT_SINK@ "$(num "${2%.*}")%" ;;
    mute) pactl set-sink-mute @DEFAULT_SINK@ toggle ;;
    # Floor at 5% so a stray drag can't black out the panel.
    bright) b=$(num "${2%.*}"); brightnessctl -q -d "$BACKLIGHT" s "$(( b < 5 ? 5 : b ))%" ;;
    prev|next) playerctl "$1" ;;
    play) playerctl play-pause ;;
    *) echo "usage: $0 status|toggle|close|mic|kbd|hz|wifi|updates|vol N|mute|bright N|prev|play|next" >&2; exit 1 ;;
esac
