#!/bin/bash
# Launch only this desktop's themed panels; Battery Saver keeps them stopped.
set -euo pipefail

directory=$(dirname "$(readlink -f "$0")")
runtime=${XDG_RUNTIME_DIR:-/run/user/$UID}
if (($#)); then
    for name in "$@"; do
        [[ $name == "${name##*/}" && $name == *.conf && -f $directory/$name ]] || exit 2
    done
fi
exec 9>"$runtime/conky-start.lock"
flock 9
/usr/bin/python3 "$directory/../scripts/battery-mode.py" conky-stop
[[ -f $runtime/thomas-battery-mode/active ]] && exit 0

source "$directory/../theme.sh"
TEMP_DIR="$runtime/thomas-conky"
[[ ! -L $TEMP_DIR && ( ! -e $TEMP_DIR || -d $TEMP_DIR ) ]] || exit 1
mkdir -p -m 700 "$TEMP_DIR"
shopt -s nullglob
sources=("$directory/"*.conf)
if (($#)); then
    sources=()
    for name in "$@"; do sources+=("$directory/$name"); done
fi
for source_cfg in "${sources[@]}"; do
    temp_cfg="$TEMP_DIR/$(basename "$source_cfg")"
    {
        printf '%s\n' "-- thomas-conky: $(dirname "$directory")"
        sed -e "s/{{CONKY_COLOR1}}/${CONKY_COLOR1:-6E8898}/g" \
            -e "s/{{CONKY_COLOR2}}/${CONKY_COLOR2:-C9C9C9}/g" \
            -e "s/{{CONKY_COLOR3}}/${CONKY_COLOR3:-5C6370}/g" \
            -e "s/{{CONKY_COLOR4}}/${CONKY_COLOR4:-4A5568}/g" \
            -e "s/{{CONKY_GRAPH1}}/${CONKY_GRAPH1:-6E8898}/g" \
            -e "s/{{CONKY_GRAPH2}}/${CONKY_GRAPH2:-8FA3B0}/g" \
            "$source_cfg"
    } > "$temp_cfg"
    conky --daemonize --pause=1 -c "$temp_cfg" > "$temp_cfg.log" 2>&1 9>&-
done
