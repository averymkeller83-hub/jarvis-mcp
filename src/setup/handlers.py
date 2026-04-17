"""Step execution handlers for the first-run setup flow."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import toml

from src.security.vault import CHANNEL_SECRET_KEYS, VOICE_SECRET_KEYS, vault
from src.setup.steps import SUPPORTED_CHANNELS, SetupState, complete_step

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


async def handle_welcome(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 1 — Welcome screen. Always completes."""
    assistant_name = config.get("assistant_name", "JARVIS")
    message = (
        f"I'm {assistant_name}. I work with your Claude subscription to keep "
        "your Mac organised, your projects watched, and your mornings briefed."
    )
    result = {"message": message, "assistant_name": assistant_name}
    state = complete_step(state, 1, result)
    return state, result


async def handle_personalization(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 2 — Personalise names and write to personality.toml."""
    user_name = config.get("user_name", "Sir")
    assistant_name = config.get("assistant_name", "JARVIS")

    personality_path = CONFIG_DIR / "personality.toml"
    data: dict = {}
    if personality_path.exists():
        data = toml.load(personality_path)

    data["user_display_name"] = user_name
    data["assistant_name"] = assistant_name
    personality_path.parent.mkdir(parents=True, exist_ok=True)
    with open(personality_path, "w") as f:
        toml.dump(data, f)

    result = {"user_name": user_name, "assistant_name": assistant_name}
    state = complete_step(state, 2, result)
    return state, result


async def handle_communication(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 3 — Choose channels and save per-channel credentials.

    Accepts channel-specific credentials like:
        telegram_bot_token, telegram_chat_id
        discord_bot_token, discord_server_id, discord_channel_id
        slack_bot_token, slack_channel_id
        email_smtp_host, email_smtp_port, email_username, email_password, email_imap_host, email_recipient
        imessage_target
    """
    channels = config.get("channels", ["macos_notifications"])
    primary = config.get("primary", channels[0] if channels else "macos_notifications")

    valid = [c for c in channels if c in SUPPORTED_CHANNELS]
    if not valid:
        valid = ["macos_notifications"]
    if primary not in valid:
        primary = valid[0]

    data: dict = {
        "channels": {
            "primary": primary,
            "enabled": valid,
        },
    }

    # Per-channel credential sections — secrets go to Keychain, rest to toml
    if "telegram" in valid:
        tg: dict[str, str] = {}
        if config.get("telegram_bot_token"):
            vault.store("telegram", "bot_token", config["telegram_bot_token"])
        if config.get("telegram_chat_id"):
            tg["chat_id"] = config["telegram_chat_id"]
        if tg:
            data["telegram"] = tg

    if "discord" in valid:
        dc: dict[str, str] = {}
        if config.get("discord_bot_token"):
            vault.store("discord", "bot_token", config["discord_bot_token"])
        if config.get("discord_server_id"):
            dc["server_id"] = config["discord_server_id"]
        if config.get("discord_channel_id"):
            dc["channel_id"] = config["discord_channel_id"]
        if dc:
            data["discord"] = dc

    if "slack" in valid:
        sl: dict[str, str] = {}
        if config.get("slack_bot_token"):
            vault.store("slack", "bot_token", config["slack_bot_token"])
        if config.get("slack_channel_id"):
            sl["channel_id"] = config["slack_channel_id"]
        if sl:
            data["slack"] = sl

    if "email" in valid:
        em: dict[str, str] = {}
        for key in ("smtp_host", "smtp_port", "username", "imap_host", "recipient"):
            val = config.get(f"email_{key}")
            if val:
                em[key] = val
        if config.get("email_password"):
            vault.store("email", "password", config["email_password"])
        if em:
            data["email"] = em

    imessage_target = config.get("imessage_target", "")
    if imessage_target and "imessage" in valid:
        data["imessage"] = {"target": imessage_target}

    comm_path = CONFIG_DIR / "communication.toml"
    comm_path.parent.mkdir(parents=True, exist_ok=True)
    with open(comm_path, "w") as f:
        toml.dump(data, f)

    result = {
        "primary": primary,
        "enabled": valid,
        "available": SUPPORTED_CHANNELS,
        "imessage_target": imessage_target if "imessage" in valid else None,
        "message": f"I'll reach you via {primary}. {len(valid)} channel(s) enabled.",
    }
    state = complete_step(state, 3, result)
    return state, result


async def handle_claude_connection(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 4 — Register JARVIS MCP server in Claude Desktop config.

    Writes the jarvis entry to ~/Library/Application Support/Claude/claude_desktop_config.json.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    mcp_server_path = str(project_root / "src" / "mcp_server.py")

    claude_config_path = (
        Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    )

    registered = False
    try:
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)
        if claude_config_path.exists():
            existing = json.loads(claude_config_path.read_text())
        else:
            existing = {}

        mcp_servers = existing.setdefault("mcpServers", {})
        mcp_servers["jarvis"] = {
            "command": "python3",
            "args": [mcp_server_path],
        }

        claude_config_path.write_text(json.dumps(existing, indent=2))
        registered = True
    except Exception as exc:
        logger.warning("Could not register MCP server: %s", exc)

    result = {
        "registered": registered,
        "config_path": str(claude_config_path),
        "message": "JARVIS registered in Claude Desktop." if registered else "Could not register MCP server.",
    }
    state = complete_step(state, 4, result)
    return state, result


async def handle_contacts(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 5 — Auto-import contacts from macOS Contacts.app.

    Uses AppleScript to read names and numbers, saves to contacts_nicknames.toml.
    """
    contacts = []
    try:
        script = (
            'tell application "Contacts"\n'
            '    set output to ""\n'
            '    repeat with p in people\n'
            '        set n to name of p\n'
            '        try\n'
            '            set ph to value of first phone of p\n'
            '        on error\n'
            '            set ph to ""\n'
            '        end try\n'
            '        try\n'
            '            set em to value of first email of p\n'
            '        on error\n'
            '            set em to ""\n'
            '        end try\n'
            '        set output to output & n & "\\t" & ph & "\\t" & em & linefeed\n'
            '    end repeat\n'
            '    return output\n'
            'end tell'
        )

        def _run_applescript():
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15,
            )
            return proc.stdout.strip() if proc.returncode == 0 else ""

        raw = await asyncio.to_thread(_run_applescript)
        for line in raw.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 1 and parts[0].strip():
                entry = {"name": parts[0].strip()}
                if len(parts) >= 2 and parts[1].strip():
                    entry["phone"] = parts[1].strip()
                if len(parts) >= 3 and parts[2].strip():
                    entry["email"] = parts[2].strip()
                contacts.append(entry)
    except Exception as exc:
        logger.warning("Contact import failed: %s", exc)

    # Save to config
    nicknames_path = CONFIG_DIR / "contacts_nicknames.toml"
    nicknames_path.parent.mkdir(parents=True, exist_ok=True)

    # Also accept manual nicknames from config
    nicknames = config.get("nicknames", {})
    with open(nicknames_path, "w") as f:
        toml.dump({"nicknames": nicknames, "imported_count": len(contacts)}, f)

    result = {
        "imported_count": len(contacts),
        "nickname_count": len(nicknames),
        "contacts": contacts[:10],  # Preview first 10
    }
    state = complete_step(state, 5, result)
    return state, result


async def handle_services(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 6 — Select service ecosystems."""
    services = config.get("services", ["apple"])
    result = {"services": services, "count": len(services)}
    state = complete_step(state, 6, result)
    return state, result


async def handle_scout_sources(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 7 — Enable selected Scout sources."""
    sources_to_enable = config.get("sources", [])

    sources_path = CONFIG_DIR / "scout_sources.toml"
    example_path = CONFIG_DIR / "scout_sources.example.toml"

    if sources_path.exists():
        data = toml.load(sources_path)
    elif example_path.exists():
        data = toml.load(example_path)
    else:
        data = {"sources": {}}

    sources_section = data.get("sources", {})
    enabled_count = 0
    for name in sources_to_enable:
        if name in sources_section:
            sources_section[name]["enabled"] = True
            enabled_count += 1

    data["sources"] = sources_section
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sources_path, "w") as f:
        toml.dump(data, f)

    result = {"enabled": sources_to_enable, "count": enabled_count}
    state = complete_step(state, 7, result)
    return state, result


async def handle_github_auth(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 8 — Check for gh CLI."""
    import shutil

    gh_found = shutil.which("gh") is not None
    authenticated = False
    if gh_found:
        try:
            proc = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=5,
            )
            authenticated = proc.returncode == 0
        except Exception:
            pass

    result = {
        "gh_found": gh_found,
        "authenticated": authenticated,
        "message": "GitHub CLI detected and authenticated." if authenticated
        else "GitHub CLI not found or not authenticated." if not gh_found
        else "GitHub CLI found but not authenticated.",
    }
    state = complete_step(state, 8, result)
    return state, result


async def handle_obsidian_vault(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 9 — Link Obsidian vault path.

    Validates the vault directory exists and has an .obsidian folder.
    """
    vault_path = config.get("vault_path", "")
    valid = False
    obsidian_mcp_found = False

    if vault_path:
        vp = Path(vault_path).expanduser()
        if vp.exists() and (vp / ".obsidian").is_dir():
            valid = True

    # Save to jarvis.toml
    jarvis_config_path = CONFIG_DIR / "jarvis.toml"
    jarvis_config_path.parent.mkdir(parents=True, exist_ok=True)
    jarvis_data: dict = {}
    if jarvis_config_path.exists():
        try:
            jarvis_data = toml.load(jarvis_config_path)
        except Exception:
            pass
    if valid:
        jarvis_data.setdefault("obsidian", {})["vault_path"] = str(Path(vault_path).expanduser())
    with open(jarvis_config_path, "w") as f:
        toml.dump(jarvis_data, f)

    result = {
        "vault_path": vault_path,
        "valid": valid,
        "message": f"Obsidian vault linked at {vault_path}" if valid
        else "No valid Obsidian vault found." if vault_path
        else "Obsidian vault not configured (can add later).",
    }
    state = complete_step(state, 9, result)
    return state, result


async def handle_voice_setup(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 10 — Choose TTS and STT providers, save to voice.toml."""
    tts_provider = config.get("tts_provider", "macos_say")
    stt_provider = config.get("stt_provider", "macos_dictation")
    tts_api_key = config.get("tts_api_key", "")
    stt_api_key = config.get("stt_api_key", "")
    tts_voice_id = config.get("tts_voice_id", "")

    voice_data: dict = {
        "tts": {"provider": tts_provider},
        "stt": {
            "provider": stt_provider,
            "fallback_threshold": 0.7,
        },
    }
    # API keys go to Keychain, not plaintext toml
    if tts_api_key:
        vault.store("voice_tts", "api_key", tts_api_key)
    if tts_voice_id:
        voice_data["tts"]["voice_id"] = tts_voice_id
    if stt_api_key:
        vault.store("voice_stt", "api_key", stt_api_key)

    voice_path = CONFIG_DIR / "voice.toml"
    voice_path.parent.mkdir(parents=True, exist_ok=True)
    with open(voice_path, "w") as f:
        toml.dump(voice_data, f)

    result = {
        "tts_provider": tts_provider,
        "stt_provider": stt_provider,
        "message": f"Voice: TTS via {tts_provider}, STT via {stt_provider}.",
    }
    state = complete_step(state, 10, result)
    return state, result


async def handle_first_scan(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 11 — Run Scout discovery immediately."""
    from src.scout.engine import run_discovery

    cards = await run_discovery()
    result = {"scan_count": len(cards), "message": f"Scout found {len(cards)} items."}
    state = complete_step(state, 11, result)
    return state, result


def _build_first_contact(assistant_name: str, user_name: str) -> str:
    """Build the first-contact message Jarvis sends after setup completes."""
    return (
        f"Good day, {user_name}. I'm {assistant_name} — created by Avery Keller, "
        "inspired by the vision of Jarvis from Iron Man, and powered by Claude.\n\n"
        "I'm here to make your life easier. The more you share with me, the "
        "better I get — think of us as a team that sharpens each other.\n\n"
        "Here's a taste of what I can help with:\n"
        "- Finding and applying to jobs that match your skills\n"
        "- Learning new things — I'll quiz you, find resources, track progress\n"
        "- Meal planning and grocery lists for the week\n"
        "- Staying on top of deadlines at work or school\n"
        "- Morning briefings so you start every day prepared\n"
        "- Watching your projects for issues, PRs, and things that need attention\n\n"
        "To get started, I'd love to know just one thing:\n\n"
        "What's something you wish you had more time for?\n\n"
        "That'll tell me a lot about where I can help first. And don't worry "
        "— I'll always follow up with questions so you stay in the driver's "
        "seat. Nothing happens without you saying so."
    )


async def handle_done(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 12 — Send first-contact message and mark setup complete."""
    from src.setup.steps import get_step

    step2 = get_step(state, 2)
    user_name = "Sir"
    if step2 and step2.result:
        user_name = step2.result.get("user_name", "Sir")
    elif config.get("user_name"):
        user_name = config["user_name"]

    assistant_name = "JARVIS"
    if step2 and step2.result:
        assistant_name = step2.result.get("assistant_name", "JARVIS")

    step3 = get_step(state, 3)
    primary_channel = "macos_notifications"
    if step3 and step3.result:
        primary_channel = step3.result.get("primary", "macos_notifications")

    first_contact = _build_first_contact(assistant_name, user_name)

    try:
        from src.engine.notifications import Notification, send_notification

        notif = Notification(
            event_type="first_contact",
            title=f"{assistant_name} is ready",
            body=first_contact,
            channels=[primary_channel],
        )
        dispatch_result = await send_notification(notif)
    except Exception:
        dispatch_result = {"sent_to": [], "error": "dispatch failed"}

    # Persist setup completion to disk so it survives server restarts
    jarvis_config_path = CONFIG_DIR / "jarvis.toml"
    jarvis_data: dict = {}
    if jarvis_config_path.exists():
        try:
            jarvis_data = toml.load(jarvis_config_path)
        except Exception:
            pass
    jarvis_data["setup_complete"] = True
    jarvis_data["setup_completed_at"] = datetime.now(timezone.utc).isoformat()
    jarvis_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jarvis_config_path, "w") as f:
        toml.dump(jarvis_data, f)

    result = {
        "message": first_contact,
        "user_name": user_name,
        "assistant_name": assistant_name,
        "sent_via": primary_channel,
        "dispatch": dispatch_result,
    }
    state = complete_step(state, 12, result)
    return state, result


def check_docker_available() -> bool:
    """Check whether Docker/Colima is available (utility, not a setup step)."""
    import shutil
    return shutil.which("docker") is not None


STEP_HANDLERS: dict[int, callable] = {
    1: handle_welcome,
    2: handle_personalization,
    3: handle_communication,
    4: handle_claude_connection,
    5: handle_contacts,
    6: handle_services,
    7: handle_scout_sources,
    8: handle_github_auth,
    9: handle_obsidian_vault,
    10: handle_voice_setup,
    11: handle_first_scan,
    12: handle_done,
}
