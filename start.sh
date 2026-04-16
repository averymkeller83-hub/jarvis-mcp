#!/bin/bash
# Jarvis MCP launcher — uses venv Python (code-signed for launchd)
export HOME="/Users/averykeller"
export PYTHONUNBUFFERED=1
cd /Users/averykeller/Desktop/projects/jarvis-mcp
exec /Users/averykeller/Desktop/projects/jarvis-mcp/.venv/bin/python3.12 \
    -m uvicorn src.server.app:app \
    --host 127.0.0.1 \
    --port 7900 \
    --log-level info
