"""Step execution handlers for the first-run setup flow."""

from __future__ import annotations

from pathlib import Path

import toml

from src.setup.steps import SUPPORTED_CHANNELS, SetupState, complete_step

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
    """Step 3 — Choose preferred communication channels.

    Accepts:
        channels: list of channel names (e.g. ["imessage", "telegram"])
        primary: the main channel for important notifications
    """
    channels = config.get("channels", ["macos_notifications"])
    primary = config.get("primary", channels[0] if channels else "macos_notifications")

    # Validate channels
    valid = [c for c in channels if c in SUPPORTED_CHANNELS]
    if not valid:
        valid = ["macos_notifications"]
    if primary not in valid:
        primary = valid[0]

    # Save to config/communication.toml
    comm_path = CONFIG_DIR / "communication.toml"
    comm_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "channels": {
            "primary": primary,
            "enabled": valid,
        },
    }
    with open(comm_path, "w") as f:
        toml.dump(data, f)

    result = {
        "primary": primary,
        "enabled": valid,
        "available": SUPPORTED_CHANNELS,
        "message": f"I'll reach you via {primary}. {len(valid)} channel(s) enabled.",
    }
    state = complete_step(state, 3, result)
    return state, result


async def handle_claude_connection(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 4 — Detect Claude Desktop (mocked)."""
    result = {
        "detected": True,
        "tier": "pro",
        "message": "Claude Desktop detected — Pro subscription active.",
    }
    state = complete_step(state, 4, result)
    return state, result


async def handle_contacts(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 5 — Store contact nickname mappings."""
    nicknames = config.get("nicknames", {})

    nicknames_path = CONFIG_DIR / "contacts_nicknames.toml"
    nicknames_path.parent.mkdir(parents=True, exist_ok=True)
    with open(nicknames_path, "w") as f:
        toml.dump({"nicknames": nicknames}, f)

    result = {"nickname_count": len(nicknames), "nicknames": nicknames}
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

    # Load from existing or example
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
    """Step 8 — Check for gh CLI (mocked)."""
    result = {
        "gh_found": True,
        "authenticated": True,
        "message": "GitHub CLI detected and authenticated.",
    }
    state = complete_step(state, 8, result)
    return state, result


async def handle_colima_check(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 9 — Check for Docker/Colima (mocked — not found)."""
    result = {
        "docker_found": False,
        "colima_found": False,
        "offer_install": True,
        "message": "Docker/Colima not found. Install recommended for sandbox testing.",
    }
    state = complete_step(state, 9, result)
    return state, result


async def handle_briefing_prefs(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 10 — Set briefing time and Obsidian vault path."""
    briefing_time = config.get("briefing_time", "07:30")
    obsidian_vault = config.get("obsidian_vault", None)

    result = {
        "briefing_time": briefing_time,
        "obsidian_vault": obsidian_vault,
        "message": f"Briefing scheduled for {briefing_time}.",
    }
    state = complete_step(state, 10, result)
    return state, result


async def handle_voice_setup(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 11 — Test mic and TTS (mocked)."""
    result = {
        "mic_detected": True,
        "tts_working": True,
        "voice_profile": "default",
        "message": "Microphone detected. TTS engine ready.",
    }
    state = complete_step(state, 11, result)
    return state, result


async def handle_first_scan(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 12 — Run Scout discovery immediately."""
    from src.scout.engine import run_discovery

    cards = await run_discovery()
    result = {"scan_count": len(cards), "message": f"Scout found {len(cards)} items."}
    state = complete_step(state, 12, result)
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
    """Step 13 — Send first-contact message and mark setup complete."""
    from src.setup.steps import get_step

    step2 = get_step(state, 2)
    user_name = "Sir"
    if step2 and step2.result:
        user_name = step2.result.get("user_name", "Sir")
    elif config.get("user_name"):
        user_name = config["user_name"]

    # Pull assistant name from step 2 as well
    assistant_name = "JARVIS"
    if step2 and step2.result:
        assistant_name = step2.result.get("assistant_name", "JARVIS")

    # Pull chosen communication channel from step 3
    step3 = get_step(state, 3)
    primary_channel = "macos_notifications"
    if step3 and step3.result:
        primary_channel = step3.result.get("primary", "macos_notifications")

    first_contact = _build_first_contact(assistant_name, user_name)

    # Dispatch via notification system
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

    result = {
        "message": first_contact,
        "user_name": user_name,
        "assistant_name": assistant_name,
        "sent_via": primary_channel,
        "dispatch": dispatch_result,
    }
    state = complete_step(state, 13, result)
    return state, result


STEP_HANDLERS: dict[int, callable] = {
    1: handle_welcome,
    2: handle_personalization,
    3: handle_communication,
    4: handle_claude_connection,
    5: handle_contacts,
    6: handle_services,
    7: handle_scout_sources,
    8: handle_github_auth,
    9: handle_colima_check,
    10: handle_briefing_prefs,
    11: handle_voice_setup,
    12: handle_first_scan,
    13: handle_done,
}
