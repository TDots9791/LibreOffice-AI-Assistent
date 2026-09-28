#!/usr/bin/env bash
# Build the .oxt package (icons are generated if missing).
set -euo pipefail
cd "$(dirname "$0")"
[ -f src/extension/icons/ai_42.png ] || python3 tools/gen_icons.py
python3 tools/build.py
