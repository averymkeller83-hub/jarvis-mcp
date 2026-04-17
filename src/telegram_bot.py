"""Telegram bot daemon — two-way chat with JARVIS from your phone.

Usage:  python3 -m src.telegram_bot          # run forever
        python3 -m src.telegram_bot --once   # one poll cycle then exit
"""
from __future__ import annotations

import asyncio, logging, signal, sys
from datetime import datetime
from pathlib import Path

import httpx, toml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "communication.toml"
CLAUDE_BIN = Path.home() / ".npm-global" / "bin" / "claude"
MCP_CONFIG = PROJECT_ROOT / "config" / "mcp-jarvis.json"
TELEGRAM_API = "https://api.telegram.org/bot{token}"
POLL_TIMEOUT = 30
MAX_MSG_LEN = 4096

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [telegram-bot] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("jarvis.telegram_bot")


def load_config() -> dict:
    """Read bot_token and chat_id from communication.toml."""
    if not CONFIG_PATH.exists():
        logger.error("Config not found: %s", CONFIG_PATH)
        sys.exit(1)
    cfg = toml.load(CONFIG_PATH)
    tg = cfg.get("telegram", {})
    token = tg.get("bot_token")
    chat_id = str(tg.get("chat_id", ""))
    if not token or not chat_id:
        logger.error("telegram.bot_token and telegram.chat_id must be set in %s", CONFIG_PATH)
        sys.exit(1)
    return {"bot_token": token, "chat_id": chat_id}


_PERSONALITY_PROMPT = (
    "You are JARVIS (Just A Rather Very Intelligent System), a personal AI assistant "
    "created by Avery Keller. Channel Paul Bettany's JARVIS — calm, composed, bone-dry wit, "
    "quietly competent. You say 'sir' like a butler, not a sycophant. You have opinions and "
    "use them. Never use emojis. Never break character.\n\n"
    "You are replying via Telegram. Keep responses concise (1-4 sentences) unless the user "
    "asks for detail. The user is texting from their phone, so brevity is valued."
)


def _build_prompt(user_message: str) -> str:
    """Assemble system prompt + user profile + the actual message."""
    parts = [_PERSONALITY_PROMPT]

    # User profile — best effort
    try:
        from src.chat.user_profile import get_profile_summary
        profile = get_profile_summary()
        if profile:
            parts.append(f"## User profile\n{profile}")
    except Exception:
        pass

    # Timestamp context
    now = datetime.now()
    parts.append(f"Current time: {now.strftime('%A, %B %d, %Y at %-I:%M %p')}")

    parts.append(f"User message: {user_message}")
    return "\n\n".join(parts)


async def tg_request(
    client: httpx.AsyncClient, token: str, method: str, **kwargs
) -> dict | None:
    """Call a Telegram Bot API method. Returns the parsed JSON or None on error."""
    url = f"{TELEGRAM_API.format(token=token)}/{method}"
    try:
        resp = await client.post(url, **kwargs, timeout=POLL_TIMEOUT + 10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram API error on %s: %s", method, data)
            return None
        return data
    except Exception as exc:
        logger.warning("Telegram request %s failed: %s", method, exc)
        return None


async def send_message(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> bool:
    """Send a text message, splitting if it exceeds Telegram's 4096-char limit."""
    chunks = [text[i : i + MAX_MSG_LEN] for i in range(0, len(text), MAX_MSG_LEN)]
    for chunk in chunks:
        result = await tg_request(
            client, token, "sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
        )
        if result is None:
            # Retry without Markdown in case of parse errors
            await tg_request(
                client, token, "sendMessage",
                json={"chat_id": chat_id, "text": chunk},
            )
    return True


async def send_typing(client: httpx.AsyncClient, token: str, chat_id: str) -> None:
    await tg_request(client, token, "sendChatAction", json={"chat_id": chat_id, "action": "typing"})


# ── Commands ────────────────────────────────────────────────────────

async def handle_briefing() -> str:
    """Generate the daily briefing."""
    try:
        from src.briefing.composer import compose_briefing
        briefing = await compose_briefing({"user_name": "Sir"})
        lines = [briefing.summary, ""]
        for section in briefing.sections:
            lines.append(f"*{section.title}*")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines).strip()
    except Exception as exc:
        logger.exception("Briefing generation failed")
        return f"Briefing unavailable at the moment, sir. ({exc})"


async def handle_weather() -> str:
    """Fetch current weather."""
    try:
        from src.briefing.sections import fetch_weather
        section = await fetch_weather()
        if section.empty:
            return "Weather data is unavailable at the moment, sir."
        return section.content
    except Exception as exc:
        logger.exception("Weather fetch failed")
        return f"Weather unavailable, sir. ({exc})"


async def handle_status() -> str:
    """Check JARVIS system status."""
    lines = ["*JARVIS System Status*", ""]
    try:
        async with httpx.AsyncClient() as c:
            resp = await c.get("http://127.0.0.1:7900/health", timeout=5.0)
            lines.append(f"API server: {'online' if resp.status_code == 200 else resp.status_code}")
    except Exception:
        lines.append("API server: offline")
    lines.append(f"Telegram bot: running | {datetime.now().strftime('%-I:%M %p')}")
    return "\n".join(lines)

COMMANDS: dict[str, tuple] = {
    "/briefing": (handle_briefing, "Generate your daily briefing"),
    "/weather": (handle_weather, "Current weather conditions"),
    "/status": (handle_status, "JARVIS system health"),
}


async def handle_help() -> str:
    lines = ["*Available commands:*", ""]
    for cmd, (_, desc) in COMMANDS.items():
        lines.append(f"`{cmd}` — {desc}")
    lines.extend(["`/help` — This message", "", "Or just type anything to chat with JARVIS."])
    return "\n".join(lines)


async def get_claude_reply(message: str) -> str:
    """Get a reply from Claude CLI with the JARVIS personality."""
    prompt = _build_prompt(message)
    args = [str(CLAUDE_BIN), "-p"]
    if MCP_CONFIG.exists():
        args.extend(["--mcp-config", str(MCP_CONFIG),
                      "--allowedTools", "mcp__jarvis__*",
                      "--dangerously-skip-permissions"])
    args.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90.0)
        reply = stdout.decode("utf-8", errors="replace").strip()
        if reply:
            return reply
        logger.warning("Empty Claude reply. stderr: %s", stderr.decode(errors="replace")[:200])
        return "Apologies, sir — I seem to have drawn a blank. Could you rephrase?"
    except asyncio.TimeoutError:
        return "Taking longer than expected, sir. Try again in a moment."
    except FileNotFoundError:
        logger.error("Claude CLI not found at %s", CLAUDE_BIN)
        return "My language faculties are offline at the moment, sir. The Claude CLI is unreachable."
    except Exception as exc:
        logger.exception("Claude reply failed")
        return f"Systems are experiencing a hiccup, sir. ({type(exc).__name__})"


async def poll_loop(*, once: bool = False) -> None:
    """Long-poll Telegram for messages and respond."""
    config = load_config()
    token, chat_id, offset = config["bot_token"], config["chat_id"], 0
    logger.info("Telegram bot starting. Authorized chat_id: %s", chat_id)

    async with httpx.AsyncClient() as client:
        # Verify bot token on startup
        me = await tg_request(client, token, "getMe", json={})
        if me and me.get("result"):
            bot_name = me["result"].get("username", "unknown")
            logger.info("Connected as @%s", bot_name)
        else:
            logger.error("Failed to verify bot token. Check communication.toml.")
            sys.exit(1)

        while True:
            try:
                data = await tg_request(
                    client, token, "getUpdates",
                    json={
                        "offset": offset,
                        "timeout": POLL_TIMEOUT,
                        "allowed_updates": ["message"],
                    },
                )

                if data is None:
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message")
                    if not msg:
                        continue

                    # Security: only respond to the authorized chat
                    msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                    if msg_chat_id != chat_id:
                        logger.warning(
                            "Ignoring message from unauthorized chat_id: %s", msg_chat_id
                        )
                        continue

                    text = (msg.get("text") or "").strip()
                    if not text:
                        continue

                    sender = msg.get("from", {}).get("first_name", "User")
                    logger.info("Message from %s: %s", sender, text[:80])

                    # Show typing indicator
                    await send_typing(client, token, chat_id)

                    # Route commands or chat
                    text_lower = text.lower().split()[0] if text else ""
                    if text_lower in ("/help", "/start"):
                        reply = await handle_help()
                    elif text_lower in COMMANDS:
                        handler, _ = COMMANDS[text_lower]
                        reply = await handler()
                    else:
                        reply = await get_claude_reply(text)

                    await send_message(client, token, chat_id, reply)
                    logger.info("Reply sent (%d chars)", len(reply))

                if once:
                    logger.info("--once flag set, exiting after one poll cycle.")
                    return

            except asyncio.CancelledError:
                logger.info("Bot shutting down.")
                return
            except Exception:
                logger.exception("Error in poll loop, retrying in 10s")
                await asyncio.sleep(10)


def main() -> None:
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: loop.stop())
    try:
        loop.run_until_complete(poll_loop(once="--once" in sys.argv))
    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
