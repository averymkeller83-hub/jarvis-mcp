# JARVIS Onboarding & MCP Server — Ready to Test

## Goal

Get the JARVIS MCP server fully configured and testable in Claude Desktop for any new user. The setup wizard is the onramp: it collects credentials, registers JARVIS as an MCP server in Claude Desktop, wires up messaging channels, imports contacts, links Obsidian, and verifies everything works. By the end of setup, the user opens Claude Desktop and JARVIS tools are available.

## Architecture

The MCP server (`src/mcp_server.py`) already works — 9 tools exposed via FastMCP over stdio. The gap is onboarding: getting a fresh user from zero to "JARVIS is in my Claude Desktop and responding on Telegram." This spec covers the setup wizard improvements and messaging backend needed to close that gap.

The primary user experience is Claude Desktop + MCP. The dashboard chat (`/chat`) remains Avery's personal tool — other users talk to JARVIS through Claude Desktop using their own Claude subscription.

## Tech Stack

- Python 3.12, FastAPI, FastMCP
- httpx (Telegram API), discord.py (Discord bot), slack-sdk (Slack bot)
- smtplib/imaplib (Email — stdlib)
- AppleScript via osascript (iMessage, macOS Contacts)
- TOML config files

---

## Setup Wizard — 12 Steps

The wizard drops from 13 to 12 steps. Step 9 (Colima/Docker check) is removed from setup but retained as a runtime utility. Steps renumber accordingly.

### Step 1: Welcome
No change. Displays intro message.

### Step 2: Personalization
No change. Collects user display name and assistant name. Writes to `config/personality.toml`.

### Step 3: Communication Channels (EXPANDED)

Six two-way messaging channels. User checks which they want, credential fields appear per channel. All channels support both outbound (JARVIS sends) and inbound (user messages JARVIS, gets a response).

#### iMessage
- **Fields:** Phone number or Apple ID email
- **Validation:** Non-empty, basic phone/email format check
- **Outbound:** AppleScript via Messages.app (already working)
- **Inbound:** Poll `~/Library/Messages/chat.db` for new rows every 5 seconds
- **Notes:** Mac-only. Phone numbers normalized (strip spaces/dashes).

#### Telegram
- **Fields:** Bot token (from @BotFather), Chat ID
- **Validation:** Token format matches `digits:alphanumeric`, chat ID is numeric
- **Connection test:** Call `getMe` on Telegram Bot API to verify token
- **Outbound:** `sendMessage` via Telegram Bot API
- **Inbound:** `getUpdates` long-polling (blocks until message arrives)
- **Help text:** "Create a bot at @BotFather on Telegram, then start a chat with it and paste the token and your chat ID here."

#### Discord
- **Fields:** Bot token, Server ID, Channel ID
- **Validation:** Token non-empty, IDs are numeric
- **Connection test:** Bot login test
- **Outbound:** REST API `POST /channels/{id}/messages`
- **Inbound:** WebSocket gateway connection, listen for DMs
- **Help text:** "Create a bot at discord.com/developers, invite it to your server, paste the token and IDs here."

#### Slack
- **Fields:** Bot token, Channel ID
- **Validation:** Token starts with `xoxb-`, channel ID non-empty
- **Connection test:** `auth.test` API call
- **Outbound:** `chat.postMessage` via Slack Web API
- **Inbound:** Socket Mode WebSocket connection
- **Help text:** "Create a Slack app at api.slack.com, install it to your workspace, paste the bot token and channel ID here."

#### Email
- **Fields:** SMTP server, SMTP port (default 587), username/email, app password, IMAP server, recipient email
- **Validation:** Non-empty fields, port is numeric
- **Connection test:** SMTP + IMAP connection test
- **Outbound:** `smtplib.SMTP` with TLS
- **Inbound:** IMAP IDLE or poll every 30 seconds
- **Help text:** "For Gmail, use an App Password (not your regular password). SMTP: smtp.gmail.com, IMAP: imap.gmail.com."

#### macOS Notifications
- **Fields:** None — checkbox only
- **Outbound:** `osascript` display notification (already working)
- **Inbound:** N/A — one-way only, notification channel
- **Notes:** Always available on Mac. No credentials needed.

#### Config Storage

All channel credentials stored in `config/communication.toml`:

```toml
[channels]
primary = "telegram"
enabled = ["telegram", "imessage", "macos"]

[imessage]
target = "+18121234567"

[telegram]
bot_token = "123456:ABC-DEF1234..."
chat_id = "987654321"

[discord]
bot_token = "MTIz..."
server_id = "111222333"
channel_id = "444555666"

[slack]
bot_token = "xoxb-..."
channel_id = "C01234567"

[email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
username = "user@gmail.com"
password = "app-password-here"
imap_host = "imap.gmail.com"
recipient = "user@gmail.com"
```

### Step 4: Claude Desktop + MCP Registration (REAL)

Replace the current mock with actual detection and registration.

**Flow:**
1. Check if `/Applications/Claude.app` exists
2. Read Claude Desktop config at `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Check if `jarvis` is already registered as an MCP server
4. If not: auto-add the jarvis entry with the correct path to `scripts/jarvis-mcp-server.sh`
5. If yes: show checkmark, already configured
6. Verify the MCP server process can start (spawn it, send initialize, confirm response)

**Generated config snippet:**
```json
{
  "mcpServers": {
    "jarvis": {
      "command": "/absolute/path/to/jarvis-mcp/scripts/jarvis-mcp-server.sh",
      "args": []
    }
  }
}
```

Path is dynamically resolved from the JARVIS installation directory. The entry is merged into the existing Claude Desktop config — existing MCP servers are preserved.

**Fallback:** If Claude Desktop is not installed, show instructions to install it and a "Retry" button. This step is required. If the config file doesn't exist yet (fresh Claude Desktop install), create it with just the jarvis entry.

### Step 5: Contacts (AUTO-IMPORT)

Replace manual nickname entry with automatic macOS Contacts import.

**Flow:**
1. Read all contacts from macOS Contacts via AppleScript (or `apple-mcp` contacts tool)
2. Import name, phone numbers, email addresses
3. Store in `config/contacts.toml`
4. Display: "Found 247 contacts" with checkmark
5. User clicks Continue

**Auto-detect step** — no form, just result and Continue button. Nicknames can be added later in Settings.

### Step 6: Services
No change. Select service ecosystems (Apple, Google, GitHub, Linear, Notion).

### Step 7: Scout Sources
No change. Enable discovery sources (HackerNews, GitHub Trending, Product Hunt, arXiv).

### Step 8: GitHub Auth
No change. Check for `gh` CLI authentication.

### Step 9: Obsidian Vault (EXPANDED)

Upgrade from a simple path input to full validation and MCP integration.

**Flow:**
1. Text field for vault folder path (or file picker)
2. Validate path exists and contains `.obsidian/` subfolder
3. Check if `obsidian` MCP server is registered in Claude Desktop config
4. If not: offer to auto-add it (same merge approach as Step 4)
5. Create folder structure in vault if missing:
   - `Daily Notes/` — where briefings are written
   - `JARVIS/` — for JARVIS-generated notes and research
6. Test write — create a small test note to confirm write access
7. Store vault path in `config/briefing.toml`

### Step 10: Voice Setup (EXPANDED)

User picks their TTS and STT providers and enters credentials.

#### TTS Providers (text-to-speech)

| Provider | Fields | Notes |
|----------|--------|-------|
| Fish Audio | API key | JARVIS voice clone possible |
| Claude TTS | None — uses Claude subscription | No extra key |
| ElevenLabs | API key | Popular alternative |
| OpenAI TTS | API key | Good quality |
| System (macOS) | None — uses `say` command | Free, lowest quality |

#### STT Providers (speech-to-text)

| Provider | Fields | Notes |
|----------|--------|-------|
| Whisper (local) | None — runs on device | Free, private, needs model download |
| OpenAI Whisper API | API key | Fast, accurate, cloud |
| Deepgram | API key | Real-time streaming |
| System (macOS) | None — uses macOS dictation | Free, built-in |

#### Flow
1. Pick TTS provider from dropdown, enter API key if needed
2. Test TTS — plays "Good evening, sir" through selected provider
3. Pick STT provider from dropdown, enter API key if needed
4. Test STT — record a short phrase, transcribe it, show result
5. Store both in `config/voice.toml`

#### Config Storage

```toml
[tts]
provider = "fish_audio"
api_key = "sk-..."

[stt]
provider = "whisper_local"
model = "base"
```

### Step 11: First Scan
No change. Run initial Scout discovery.

### Step 12: Done

Setup complete. Sends first-contact greeting via the primary two-way channel. Creates user account (username + password for dashboard access). The message listener starts automatically on next server boot — setup writes the config, the server reads it on startup.

---

## Message Listener Service

Background service that polls/listens on all enabled two-way channels for incoming messages and routes them through Claude with MCP tools.

### Module

New file: `src/hands/listener.py`

### Architecture

- Registered as an async task in the ProactiveEngine
- One poller/listener coroutine per enabled channel
- Started after setup completes or on server boot if channels are configured

### Per-Channel Polling

| Channel | Method | Latency |
|---------|--------|---------|
| iMessage | Poll `~/Library/Messages/chat.db` | ~5s |
| Telegram | `getUpdates` long-poll | Near-instant |
| Discord | WebSocket gateway | Real-time |
| Slack | Socket Mode WebSocket | Real-time |
| Email | IMAP IDLE or poll | ~30s |

### Message Flow

```
User sends message on channel
  → Listener detects incoming message
  → Classify via brain router (Surface)
  → Route through _claude_reply() with MCP tools
  → Send response back on same channel
```

### Config

Reads `config/communication.toml` to determine which channels are enabled and their credentials. Listener only starts pollers for channels listed in `enabled`.

---

## Messaging Backend — Channel Implementations

### File Structure

```
src/hands/
  messaging.py      — iMessage send (existing) + iMessage poll (new)
  telegram.py       — Telegram Bot API send + getUpdates poll (new)
  discord_bot.py    — Discord bot gateway + REST send (new)
  slack_bot.py      — Slack Socket Mode + chat.postMessage (new)
  email_client.py   — SMTP send + IMAP receive (new)
  listener.py       — Unified listener service (new)
```

### Shared Interface

Each channel module exports:

```python
async def send(config: dict, message: str) -> SendResult
async def poll(config: dict, since: Any) -> list[IncomingMessage]
```

`SendResult` and `IncomingMessage` are dataclasses defined in a shared `src/hands/types.py`.

### Notification System Update

`src/engine/notifications.py` updated to:
- Replace Telegram stub with real `telegram.send()` call
- Add Discord, Slack, Email dispatch
- Read per-channel credentials from `communication.toml` sections

### Dependencies

Added to `pyproject.toml`:
- `discord.py` — Discord bot gateway and REST API
- `slack-sdk` — Slack Socket Mode and Web API

No new deps for Telegram (httpx already present) or Email (stdlib).

---

## MCP Server Tools

The existing MCP server (`src/mcp_server.py`) already exposes 9 tools:

1. `get_weather` — Current weather
2. `get_briefing` — Morning briefing with weather, news, calendar
3. `send_imessage` — Send iMessage to a contact
4. `get_status` — JARVIS system status
5. `run_scout` — Scout discovery scan
6. `get_lessons` — List learned lessons
7. `set_reminder` — macOS Reminders
8. `open_app` — Launch macOS app
9. `get_calendar_today` — Today's calendar events

### New Tools to Add

With the messaging backend, add tools for each channel:

- `send_telegram` — Send a Telegram message
- `send_discord` — Send a Discord message
- `send_slack` — Send a Slack message
- `send_email` — Send an email
- `send_notification` — Send via primary channel (auto-routes)

These are exposed through the MCP server so Claude Desktop can use them directly.

---

## Runtime Docker/Colima Check

Removed from setup but kept as a utility. When JARVIS needs sandboxed execution at runtime:

```python
from src.setup.handlers import check_docker_available

available = await check_docker_available()
if not available:
    # Fall back to non-sandboxed execution or inform user
```

The function checks for Docker and Colima binaries and whether the Docker daemon is running.

---

## What "Ready to Test" Means

After setup completes, a tester should be able to:

1. Open Claude Desktop
2. See JARVIS tools in the MCP tools list
3. Say "What's the weather?" → Claude uses `get_weather` tool → real weather data
4. Say "Send me a Telegram message saying hello" → Claude uses `send_telegram` → message arrives on their phone
5. Say "What's on my calendar?" → Claude uses `get_calendar_today` → real calendar events
6. Message JARVIS on Telegram → get a response back
7. Say "Save a note about this in my vault" → Obsidian MCP writes to their vault

All using the tester's own Claude subscription, their own Telegram bot, their own Obsidian vault.
