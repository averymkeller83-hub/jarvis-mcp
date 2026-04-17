#!/bin/bash
# Install or uninstall the JARVIS MCP LaunchAgent.
# Usage:
#   ./scripts/install-launchagent.sh          # install
#   ./scripts/install-launchagent.sh uninstall # uninstall

set -euo pipefail

LABEL="com.jarvis-mcp.daemon"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.jarvis-mcp.daemon.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON3="$(which python3)"

uninstall() {
    echo "Stopping $LABEL..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST_DST"
    echo "Uninstalled."
}

install() {
    # Stop existing if loaded
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

    # Ensure log directory
    mkdir -p "$LOG_DIR"

    # Template the plist with actual paths
    sed \
        -e "s|__PYTHON3__|$PYTHON3|g" \
        -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
        "$PLIST_SRC" > "$PLIST_DST"

    # Load
    launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

    echo "Installed and started $LABEL"
    echo "  Logs: $LOG_DIR/daemon.{stdout,stderr}.log"
    echo "  Stop: launchctl bootout gui/$(id -u)/$LABEL"
}

if [ "${1:-}" = "uninstall" ]; then
    uninstall
else
    install
fi
