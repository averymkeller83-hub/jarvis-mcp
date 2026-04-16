"""Step execution handlers for the first-run setup flow."""

from __future__ import annotations

from pathlib import Path

import toml

from src.setup.steps import SetupState, complete_step

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


async def handle_claude_connection(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 3 — Detect Claude Desktop (mocked)."""
    result = {
        "detected": True,
        "tier": "pro",
        "message": "Claude Desktop detected — Pro subscription active.",
    }
    state = complete_step(state, 3, result)
    return state, result


async def handle_contacts(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 4 — Store contact nickname mappings."""
    nicknames = config.get("nicknames", {})

    nicknames_path = CONFIG_DIR / "contacts_nicknames.toml"
    nicknames_path.parent.mkdir(parents=True, exist_ok=True)
    with open(nicknames_path, "w") as f:
        toml.dump({"nicknames": nicknames}, f)

    result = {"nickname_count": len(nicknames), "nicknames": nicknames}
    state = complete_step(state, 4, result)
    return state, result


async def handle_services(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 5 — Select service ecosystems."""
    services = config.get("services", ["apple"])
    result = {"services": services, "count": len(services)}
    state = complete_step(state, 5, result)
    return state, result


async def handle_scout_sources(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 6 — Enable selected Scout sources."""
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
    state = complete_step(state, 6, result)
    return state, result


async def handle_github_auth(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 7 — Check for gh CLI (mocked)."""
    result = {
        "gh_found": True,
        "authenticated": True,
        "message": "GitHub CLI detected and authenticated.",
    }
    state = complete_step(state, 7, result)
    return state, result


async def handle_colima_check(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 8 — Check for Docker/Colima (mocked — not found)."""
    result = {
        "docker_found": False,
        "colima_found": False,
        "offer_install": True,
        "message": "Docker/Colima not found. Install recommended for sandbox testing.",
    }
    state = complete_step(state, 8, result)
    return state, result


async def handle_briefing_prefs(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 9 — Set briefing time and Obsidian vault path."""
    briefing_time = config.get("briefing_time", "07:30")
    obsidian_vault = config.get("obsidian_vault", None)

    result = {
        "briefing_time": briefing_time,
        "obsidian_vault": obsidian_vault,
        "message": f"Briefing scheduled for {briefing_time}.",
    }
    state = complete_step(state, 9, result)
    return state, result


async def handle_voice_setup(
    state: SetupState, config: dict
) -> tuple[SetupState, dict]:
    """Step 10 — Test mic and TTS (mocked)."""
    result = {
        "mic_detected": True,
        "tts_working": True,
        "voice_profile": "default",
        "message": "Microphone detected. TTS engine ready.",
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


async def handle_done(state: SetupState, config: dict) -> tuple[SetupState, dict]:
    """Step 12 — Completion message using user's name."""
    # Pull user name from step 2 result, or fall back to config / default
    from src.setup.steps import get_step

    step2 = get_step(state, 2)
    user_name = "Sir"
    if step2 and step2.result:
        user_name = step2.result.get("user_name", "Sir")
    elif config.get("user_name"):
        user_name = config["user_name"]

    message = f"Ready when you are, {user_name}."
    result = {"message": message, "user_name": user_name}
    state = complete_step(state, 12, result)
    return state, result


STEP_HANDLERS: dict[int, callable] = {
    1: handle_welcome,
    2: handle_personalization,
    3: handle_claude_connection,
    4: handle_contacts,
    5: handle_services,
    6: handle_scout_sources,
    7: handle_github_auth,
    8: handle_colima_check,
    9: handle_briefing_prefs,
    10: handle_voice_setup,
    11: handle_first_scan,
    12: handle_done,
}
