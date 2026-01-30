#!/bin/bash
# Update cached values for polybar panel

# Updates count
if command -v checkupdates &>/dev/null; then
    count=$(checkupdates 2>/dev/null | wc -l)
elif command -v apt &>/dev/null; then
    count=$(apt list --upgradable 2>/dev/null | grep -c upgradable)
else
    count=0
fi
echo "UPD:$count" > /tmp/polybar-updates-cache

# GPU detection
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    echo "GPU:NV" > /tmp/polybar-gpu-cache
elif lspci 2>/dev/null | grep -qi "amd.*radeon\|amd.*graphics"; then
    echo "GPU:AMD" > /tmp/polybar-gpu-cache  
else
    echo "GPU:INT" > /tmp/polybar-gpu-cache
fi
