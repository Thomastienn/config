#!/bin/bash
# Kill existing conky instances
killall conky 2>/dev/null

# Load centralized theme
source ~/thomas_config/theme.sh

# Create temp directory for generated configs
TEMP_DIR="/tmp/conky_$$"
mkdir -p "$TEMP_DIR"

# Generate configs from source files with theme colors
shopt -s nullglob
for source_cfg in ~/thomas_config/conky/*.conf; do
  [ -f "$source_cfg" ] || continue
  
  temp_cfg="$TEMP_DIR/$(basename "$source_cfg")"
  
  # Replace color placeholders with theme colors
  sed -e "s/{{CONKY_COLOR1}}/${CONKY_COLOR1}/g" \
      -e "s/{{CONKY_COLOR2}}/${CONKY_COLOR2}/g" \
      -e "s/{{CONKY_COLOR3}}/${CONKY_COLOR3}/g" \
      -e "s/{{CONKY_COLOR4}}/${CONKY_COLOR4}/g" \
      -e "s/{{CONKY_GRAPH1}}/${CONKY_GRAPH1}/g" \
      -e "s/{{CONKY_GRAPH2}}/${CONKY_GRAPH2}/g" \
      "$source_cfg" > "$temp_cfg"
  
  # Start conky with generated config
  conky --daemonize --pause=1 -c "$temp_cfg"
done
