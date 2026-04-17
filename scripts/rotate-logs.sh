#!/bin/bash
# Rotate JARVIS daemon logs — keeps last 5 rotations, max 10MB each.
# Add to cron or run periodically.

set -euo pipefail

LOG_DIR="$(cd "$(dirname "$0")/.." && pwd)/logs"
MAX_SIZE=$((10 * 1024 * 1024))  # 10MB
MAX_ROTATIONS=5

rotate() {
    local file="$1"
    [ -f "$file" ] || return

    local size
    size=$(stat -f%z "$file" 2>/dev/null || echo 0)
    [ "$size" -lt "$MAX_SIZE" ] && return

    # Shift older rotations
    for i in $(seq $((MAX_ROTATIONS - 1)) -1 1); do
        [ -f "${file}.$i" ] && mv "${file}.$i" "${file}.$((i + 1))"
    done
    [ -f "${file}.$MAX_ROTATIONS" ] && rm -f "${file}.$MAX_ROTATIONS"

    mv "$file" "${file}.1"
    touch "$file"
    echo "Rotated $file"
}

rotate "$LOG_DIR/daemon.stdout.log"
rotate "$LOG_DIR/daemon.stderr.log"
