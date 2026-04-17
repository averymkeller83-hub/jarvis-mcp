#!/bin/bash
# Switch Claude Desktop between lean (daily JARVIS) and full (dev) configs
# Usage: ./switch-config.sh lean|full

CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CONFIG_DIR="$(dirname "$0")/../config"

case "$1" in
    lean)
        cp "$CONFIG_DIR/claude-desktop-lean.json" "$CLAUDE_CONFIG"
        echo "Switched to LEAN config (3 servers: jarvis + github + memory)"
        echo "Restart Claude Desktop to apply."
        ;;
    full)
        cp "$CONFIG_DIR/claude-desktop-full.json" "$CLAUDE_CONFIG"
        echo "Switched to FULL config (8 servers: all tools loaded)"
        echo "Restart Claude Desktop to apply."
        ;;
    *)
        echo "Usage: $0 lean|full"
        echo "  lean — Daily JARVIS (3 servers, fast, cheap)"
        echo "  full — Dev mode (8 servers, all tools)"
        exit 1
        ;;
esac
