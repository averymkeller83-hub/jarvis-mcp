#!/bin/bash
# JARVIS MCP — One-command installer for macOS
# Usage: curl -sL <raw-url> | bash   OR   bash scripts/install.sh
set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { printf "${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "${RED}✗ %s${NC}\n" "$1"; exit 1; }
info() { printf "${CYAN}→${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}⚠${NC} %s\n" "$1"; }
printf "\n${BOLD}JARVIS MCP Installer${NC}  —  macOS only\n\n"

# ── 1. Prerequisites ─────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || fail "This installer only supports macOS."
info "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || fail "python3 not found. Install via Xcode CLT or Homebrew."
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=${PY_VER%%.*}; PY_MINOR=${PY_VER##*.}
(( PY_MAJOR >= 3 && PY_MINOR >= 9 )) || fail "Python 3.9+ required (found $PY_VER)."
ok "Python $PY_VER"
CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
if [[ -d "$CLAUDE_CONFIG_DIR" ]]; then ok "Claude Desktop detected"
else warn "Claude Desktop not found — you can register the server manually later."; fi
if command -v gh >/dev/null 2>&1; then ok "gh CLI available"
else warn "gh CLI not found — optional, install with: brew install gh"; fi

# ── 2. Locate / clone repo ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/../src/mcp_server.py" ]]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    ok "Running from existing repo: $PROJECT_DIR"
else
    PROJECT_DIR="$HOME/Desktop/projects/jarvis-mcp"
    if [[ -d "$PROJECT_DIR/.git" ]]; then ok "Repo already cloned at $PROJECT_DIR"
    else
        info "Cloning jarvis-mcp..."
        mkdir -p "$(dirname "$PROJECT_DIR")"
        git clone https://github.com/averykeller/jarvis-mcp.git "$PROJECT_DIR"
        ok "Cloned to $PROJECT_DIR"
    fi
fi

# ── 3. Python dependencies ──────────────────────────────────────
info "Installing Python dependencies..."
VENV_DIR="$PROJECT_DIR/.venv"
[[ -d "$VENV_DIR" ]] || python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q toml httpx mcp pydantic pydantic-settings
ok "Dependencies installed in .venv"

# ── 4. Config: jarvis.toml ──────────────────────────────────────
CONFIG_DIR="$PROJECT_DIR/config"
JARVIS_TOML="$CONFIG_DIR/jarvis.toml"
if [[ -f "$JARVIS_TOML" ]]; then
    ok "jarvis.toml already exists — skipping (won't overwrite)"
else
    cp "$CONFIG_DIR/jarvis.example.toml" "$JARVIS_TOML"
    # ── 5. Auto-detect location via IP ───────────────────────────
    info "Detecting location..."
    GEO=$(curl -sf --max-time 5 "https://ipinfo.io/json" || echo "")
    if [[ -n "$GEO" ]]; then
        CITY=$(echo "$GEO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('city','Unknown'))" 2>/dev/null || echo "Unknown")
        REGION=$(echo "$GEO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('region',''))" 2>/dev/null || echo "")
        LOC_STR=$(echo "$GEO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('loc','39.1653,-86.5264'))" 2>/dev/null || echo "39.1653,-86.5264")
        LAT="${LOC_STR%%,*}"; LON="${LOC_STR##*,}"
        LOCATION_NAME="$CITY${REGION:+, $REGION}"
        python3 -c "
import toml
p='$JARVIS_TOML'; c=toml.load(p)
c['location']={'name':'$LOCATION_NAME','latitude':$LAT,'longitude':$LON}
with open(p,'w') as f: toml.dump(c,f)
"
        ok "Location set to $LOCATION_NAME ($LAT, $LON)"
    else
        warn "Could not detect location — using default (edit config/jarvis.toml)"
    fi
    # ── 6. Ask user's name ───────────────────────────────────────
    MACOS_NAME=$(id -F 2>/dev/null | awk '{print $1}' || echo "")
    DEFAULT_NAME="${MACOS_NAME:-Sir}"
    printf "${CYAN}→${NC} What should JARVIS call you? [${BOLD}$DEFAULT_NAME${NC}]: "
    read -r USER_NAME
    USER_NAME="${USER_NAME:-$DEFAULT_NAME}"
    python3 -c "
import toml
p='$JARVIS_TOML'; c=toml.load(p)
c.setdefault('personality',{})['user_display_name']='$USER_NAME'
c['setup_complete']=True
with open(p,'w') as f: toml.dump(c,f)
"
    ok "JARVIS will call you \"$USER_NAME\""
fi

# ── 7. Register MCP server in Claude Desktop ────────────────────
CLAUDE_CONFIG="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"
SERVER_SCRIPT="$PROJECT_DIR/scripts/jarvis-mcp-server.sh"
chmod +x "$SERVER_SCRIPT" 2>/dev/null || true
if [[ -d "$CLAUDE_CONFIG_DIR" ]]; then
    info "Registering JARVIS in Claude Desktop..."
    JARVIS_ENTRY="{\"command\":\"$SERVER_SCRIPT\",\"args\":[]}"
    if [[ -f "$CLAUDE_CONFIG" ]]; then EXISTING=$(cat "$CLAUDE_CONFIG")
    else EXISTING='{"mcpServers":{}}'; fi
    if command -v jq >/dev/null 2>&1; then
        echo "$EXISTING" | jq --argjson srv "$JARVIS_ENTRY" '.mcpServers.jarvis = $srv' > "$CLAUDE_CONFIG.tmp"
        mv "$CLAUDE_CONFIG.tmp" "$CLAUDE_CONFIG"
    else
        python3 -c "
import json
cfg=json.loads('''$EXISTING''')
cfg.setdefault('mcpServers',{})['jarvis']=json.loads('$JARVIS_ENTRY')
with open('$CLAUDE_CONFIG','w') as f: json.dump(cfg,f,indent=2)
"
    fi
    ok "JARVIS MCP server registered in Claude Desktop"
else
    warn "Skipped Claude Desktop registration (not installed)"
fi

# ── 8. Finalize ─────────────────────────────────────────────────
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/cache" "$PROJECT_DIR/memory"
printf "\n${GREEN}${BOLD}JARVIS is ready.${NC}\n\n"
printf "  Config:   ${BOLD}$JARVIS_TOML${NC}\n"
printf "  Server:   ${BOLD}$PROJECT_DIR/src/mcp_server.py${NC}\n"
printf "  Logs:     ${BOLD}$PROJECT_DIR/logs/${NC}\n\n"
printf "  ${CYAN}Next steps:${NC}\n"
printf "    1. Restart Claude Desktop to load the JARVIS MCP server\n"
printf "    2. Say \"Good morning\" — JARVIS will introduce itself\n"
printf "    3. Edit ${BOLD}config/jarvis.toml${NC} to customize further\n\n"
