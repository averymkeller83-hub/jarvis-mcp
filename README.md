<p align="center">
  <h1 align="center">JARVIS</h1>
  <p align="center"><strong>Just A Rather Very Intelligent System</strong></p>
  <p align="center">An MCP server that turns Claude Desktop into a personal AI assistant for macOS.</p>
  <p align="center">
    <a href="#install">Install</a> &nbsp;&bull;&nbsp;
    <a href="#tools">41 Tools</a> &nbsp;&bull;&nbsp;
    <a href="#usage">Usage</a> &nbsp;&bull;&nbsp;
    <a href="#telegram">Telegram Bot</a> &nbsp;&bull;&nbsp;
    <a href="#architecture">Architecture</a>
  </p>
</p>

> *"Perhaps if you used it for something other than impressing women, sir, it might hold a charge longer."*

---

**Free with any Claude subscription.** No extra API keys for core features. One config change and Claude becomes your butler.

## What It Does

You talk to Claude Desktop like normal. JARVIS gives it 41 tools to actually *do things* on your Mac -- send messages, play music, check your calendar, dispatch coding agents, control smart home devices, and learn your preferences over time.

No mode switching. No separate apps. Just one conversation.

## <a name="tools"></a>Tools (41)

| Category | Tools | What You Get |
|---|---|---|
| **Briefing & Awareness** | `get_briefing` `get_weather` `get_status` | Morning briefing, weather, system health |
| **Calendar** | `get_calendar_today` `add_calendar_event` | Read and create macOS Calendar events |
| **Reminders** | `get_reminders` `set_reminder` | Read and create macOS Reminders |
| **Email** | `get_unread_email` | Inbox summary from Mail.app |
| **Messaging** | `send_imessage` `send_telegram` `send_notification` | iMessage, Telegram, macOS notifications |
| **Contacts** | `lookup_contact` | Search macOS Contacts by name |
| **Music** | `play_music` `pause_music` `skip_track` `set_volume` | Full Apple Music control |
| **Alarms & Timers** | `set_alarm` `set_timer` | Alarms via Reminders, timers with notifications |
| **HomeKit** | `homekit_control` | Smart home via Shortcuts integration |
| **Apps** | `open_app` | Launch any macOS application |
| **Notes** | `create_note` | Create notes in Notes.app |
| **Maps** | `search_maps` | Search Apple Maps |
| **Clipboard** | `get_clipboard` `set_clipboard` | Read/write the system clipboard |
| **System** | `get_screen_time` `do_not_disturb` `open_url` | Uptime, Focus mode, URL opening |
| **Voice** | `speak` `jarvis_say` `enable_voice_mode` `disable_voice_mode` | macOS TTS with toggle-able narration |
| **Scout** | `run_scout` | Discover tools, repos, and news for your stack |
| **Lessons** | `get_lessons` `learn` | Self-improvement -- remembers corrections |
| **User Profile** | `get_user_profile` `remember_about_user` `remember_person` | Persistent memory about you and your people |
| **Code Agents** | `dispatch_code_agent` `dispatch_background_agent` `check_background_agent` `list_projects` | Spawn Claude Code agents from chat |

## <a name="install"></a>Quick Install

**Prerequisites:** macOS, Python 3.12+, [Claude Desktop](https://claude.ai/download) with any subscription.

```bash
# 1. Clone
git clone https://github.com/averymkeller83-hub/jarvis-mcp.git
cd jarvis-mcp

# 2. Create venv and install
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Copy the example config
cp config/jarvis.example.toml config/jarvis.toml

# 4. Register with Claude Desktop
```

For step 4, open Claude Desktop's config file:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add the JARVIS server:

```json
{
  "mcpServers": {
    "jarvis": {
      "command": "python3",
      "args": ["/path/to/jarvis-mcp/src/mcp_server.py"]
    }
  }
}
```

Replace `/path/to/jarvis-mcp` with your actual clone path. Restart Claude Desktop. Done.

## Configuration

### Location & Identity

Edit `config/jarvis.toml`:

```toml
[personality]
user_display_name = "Sir"          # What JARVIS calls you
assistant_name = "JARVIS"          # The assistant's name

[location]
name = "Bloomington, IN"
latitude = 39.1653
longitude = -86.5264

[voice]
enabled = false                    # Start with voice off
voice_name = "Daniel"              # macOS TTS voice (Daniel, Samantha, Alex, etc.)
```

### Messaging

Create `config/communication.toml` for iMessage and Telegram:

```toml
[channels]
primary = "telegram"
enabled = ["telegram", "macos_notifications", "imessage"]

[imessage]
allowed_senders = ["+15551234567"]

[telegram]
bot_token = "YOUR_BOT_TOKEN"
chat_id = "YOUR_CHAT_ID"
```

### Voice

Voice is off by default. Toggle it at runtime:

```
"JARVIS, enable voice mode."
"Switch to the Samantha voice."
"Go quiet."
```

Or set `voice.enabled = true` in `jarvis.toml` to start with it on.

## <a name="usage"></a>Usage Examples

Just talk to Claude Desktop. JARVIS handles the rest.

| You say | What happens |
|---|---|
| *"What's on my calendar today?"* | Reads macOS Calendar |
| *"Text Mom I'll be late for dinner"* | Looks up Mom in Contacts, sends iMessage |
| *"Play something by Radiohead"* | Searches Apple Music, starts playback |
| *"Set a timer for 15 minutes"* | Background timer with notification |
| *"Give me my morning briefing"* | Weather + calendar + email + news + reminders |
| *"Turn off the living room lights"* | HomeKit via Shortcuts |
| *"What's in my clipboard?"* | Reads clipboard contents |
| *"Remember that I prefer dark mode in all apps"* | Saves to your user profile |
| *"Fix the login bug in the clawwork project"* | Dispatches a Claude Code agent |
| *"Run a scout scan"* | Discovers tools and repos relevant to your stack |
| *"What have you learned so far?"* | Lists all stored lessons |
| *"Send a Telegram message: I'm on my way"* | Sends via your JARVIS Telegram bot |
| *"Enable voice mode"* | JARVIS starts narrating responses aloud |

## <a name="architecture"></a>Architecture

```
┌──────────────────────────────┐
│      Claude Desktop          │  Your subscription. The brain.
│      (any plan)              │
└──────────┬───────────────────┘
           │ MCP (stdio)
           ▼
┌──────────────────────────────┐
│      JARVIS MCP Server       │  41 tools. Python + FastMCP.
│      src/mcp_server.py       │  Talks to macOS via AppleScript.
├──────────────────────────────┤
│  briefing/  calendar  email  │
│  music  reminders  contacts  │
│  messaging  homekit  voice   │
│  scout  lessons  clipboard   │
│  code agents  maps  notes    │
└──────────┬───────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
  macOS APIs   Claude Code
  (osascript)  (agent dispatch)
```

JARVIS is a single MCP server. Claude Desktop connects to it over stdio. Every tool calls macOS directly via AppleScript/osascript -- no intermediate daemon required. Code agents are dispatched by shelling out to the Claude CLI.

## Lean vs. Full Config

Two pre-built Claude Desktop configs for different needs:

| Config | MCP Servers | Use Case |
|---|---|---|
| **Lean** | 3 (JARVIS + GitHub + Memory) | Daily driver. Fast. Low token overhead. |
| **Full** | 8 (+ Filesystem, Notion, Obsidian, Playwright, Context7) | Dev mode. All tools loaded. |

Switch between them:

```bash
./scripts/switch-config.sh lean    # Daily JARVIS
./scripts/switch-config.sh full    # Dev mode
# Restart Claude Desktop after switching.
```

## <a name="telegram"></a>Telegram Bot

Two-way access to JARVIS from your phone.

### Setup

1. Create a bot via [@BotFather](https://t.me/botfather) on Telegram
2. Get your chat ID (message [@userinfobot](https://t.me/userinfobot))
3. Add both to `config/communication.toml`:
   ```toml
   [telegram]
   bot_token = "123456:ABC-DEF..."
   chat_id = "your_chat_id"
   ```
4. Run the bot:
   ```bash
   python3 -m src.telegram_bot
   ```

The bot routes your messages through Claude with JARVIS personality and tools. Keep it running as a background service or use the included LaunchAgent plist in `scripts/`.

## Scout Discovery

Scout scans sources you opt into and surfaces tools, repos, and news relevant to your stack.

Configure sources in `config/scout_sources.toml`:

```toml
[sources.github_repos]
enabled = true
cadence = "hourly"

[sources.hackernews]
enabled = true
cadence = "daily"
min_score = 100
```

Available sources: Anthropic Changelog, Claude Plugin Marketplace, MCP Registry, GitHub Repos, GitHub Trending, RSS (curated + custom), Hacker News.

## Project Structure

```
src/
  mcp_server.py     # The MCP server -- all 41 tools
  telegram_bot.py   # Two-way Telegram bot
  briefing/         # Morning briefing composer
  brain/            # Router and classification
  hands/            # AppleScript / OS integrations
  scout/            # Discovery engine
  lessons/          # Correction capture and retrieval
  chat/             # User profile and history
  voice/            # TTS pipeline
  engine/           # Background tasks and scheduling
  setup/            # First-run setup flow
  settings/         # Settings manager
  integrations/     # Weather, RSS, GitHub connectors
config/             # TOML configs (copy examples, customize)
scripts/            # Config switcher, LaunchAgent installer, log rotation
tests/              # Test suite
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version:

1. Fork and branch
2. Read the spec at `docs/specs/`
3. One PR, one thing
4. Tests required
5. No walls of text

## License

[Apache 2.0](LICENSE)

## Credits

Built by [Avery Keller](https://github.com/averymkeller83-hub).

Powered by [Claude](https://claude.ai) and the [Model Context Protocol](https://modelcontextprotocol.io).

---

*"Will that be all, sir?"*
