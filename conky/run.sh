#!/bin/bash
# ================================================================
# Conky launcher with theme integration
# ================================================================

set -e

# Kill existing conky instances gracefully
if pgrep -x conky >/dev/null; then
    killall conky 2>/dev/null || true
    sleep 0.5
fi

# Load centralized theme
THEME_FILE=~/thomas_config/theme.sh
if [ ! -f "$THEME_FILE" ]; then
    echo "Error: Theme file not found at $THEME_FILE" >&2
    exit 1
fi
source "$THEME_FILE"

# Create temp directory for generated configs
TEMP_DIR="/tmp/conky_$$"
mkdir -p "$TEMP_DIR"

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT

# Generate configs from source files with theme colors
shopt -s nullglob
for source_cfg in ~/thomas_config/conky/*.conf; do
    [ -f "$source_cfg" ] || continue
    
    temp_cfg="$TEMP_DIR/$(basename "$source_cfg")"
    
    # Replace color placeholders with theme colors
    sed -e "s/{{CONKY_COLOR1}}/${CONKY_COLOR1:-6E8898}/g" \
        -e "s/{{CONKY_COLOR2}}/${CONKY_COLOR2:-C9C9C9}/g" \
        -e "s/{{CONKY_COLOR3}}/${CONKY_COLOR3:-5C6370}/g" \
        -e "s/{{CONKY_COLOR4}}/${CONKY_COLOR4:-4A5568}/g" \
        -e "s/{{CONKY_GRAPH1}}/${CONKY_GRAPH1:-6E8898}/g" \
        -e "s/{{CONKY_GRAPH2}}/${CONKY_GRAPH2:-8FA3B0}/g" \
        "$source_cfg" > "$temp_cfg"
    
    # Start conky with generated config (don't exit on failure)
    conky --daemonize --pause=1 -c "$temp_cfg" || echo "Warning: Failed to start conky with $source_cfg" >&2
done

# Keep temp files around since conky is daemonized
trap - EXIT
