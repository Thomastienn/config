#!/bin/bash
# Panel info - fast secondary system info for polybar toggle panel
# Using text labels for reliability

SEP="%{F#5C6370}|%{F-}"

# Updates (cached)
UPDATES_CACHE="/tmp/polybar-updates-cache"
if [[ -f "$UPDATES_CACHE" ]]; then
    updates=$(cat "$UPDATES_CACHE")
else
    updates="UPD:?"
fi

# GPU (cached)
GPU_CACHE="/tmp/polybar-gpu-cache"
if [[ -f "$GPU_CACHE" ]]; then
    gpu=$(cat "$GPU_CACHE")
else
    if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
        echo "GPU:NV" > "$GPU_CACHE"
    else
        echo "GPU:INT" > "$GPU_CACHE"
    fi
    gpu=$(cat "$GPU_CACHE")
fi

# Brightness
if [[ -f /sys/class/backlight/intel_backlight/brightness ]]; then
    cur=$(</sys/class/backlight/intel_backlight/brightness)
    max=$(</sys/class/backlight/intel_backlight/max_brightness)
    pct=$((cur * 100 / max))
    brightness="BRI:${pct}%"
else
    brightness=""
fi

# Mic
if pactl get-source-mute @DEFAULT_SOURCE@ 2>/dev/null | grep -q "yes"; then
    mic="MIC:OFF"
else
    mic="MIC:ON"
fi

# Keyboard layout
kbd=$(setxkbmap -query 2>/dev/null | awk '/layout/{print toupper($2)}')
kbd="KB:${kbd:-US}"

# Network
essid=$(iwgetid -r 2>/dev/null)
if [[ -n "$essid" ]]; then
    net="NET:${essid:0:8}"
else
    net="NET:--"
fi

# CPU
read -r cpu_line < /proc/stat
set -- $cpu_line
total=$(( $2+$3+$4+$5+$6+$7+$8 ))
idle=$5
LAST_CPU="/tmp/polybar-cpu-last"
if [[ -f "$LAST_CPU" ]]; then
    read last_total last_idle < "$LAST_CPU"
    diff_total=$((total - last_total))
    diff_idle=$((idle - last_idle))
    if [[ $diff_total -gt 0 ]]; then
        cpu=$((100 * (diff_total - diff_idle) / diff_total))
    else
        cpu=0
    fi
else
    cpu=0
fi
echo "$total $idle" > "$LAST_CPU"
cpu="CPU:${cpu}%"

# Memory
while read -r key val _; do
    case $key in
        MemTotal:) mem_total=$val ;;
        MemAvailable:) mem_avail=$val; break ;;
    esac
done < /proc/meminfo
mem_used=$((100 - mem_avail * 100 / mem_total))
mem="MEM:${mem_used}%"

echo "${updates} ${SEP} ${gpu} ${SEP} ${brightness} ${SEP} ${mic} ${SEP} ${kbd} ${SEP} ${net} ${SEP} ${cpu} ${SEP} ${mem}"
