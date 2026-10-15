#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3 "$(dirname "$(readlink -f "$0")")/setup/main.py" "$@"
