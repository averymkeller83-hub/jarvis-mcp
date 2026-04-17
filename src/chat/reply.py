"""Chat reply engine — multi-turn conversation via Anthropic SDK or Claude CLI fallback."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_PERSONALITY_PROMPT = (
    "You are JARVIS (Just A Rather Very Intelligent System), a personal AI assistant "
    "created by Avery Keller. Channel Paul Bettany's JARVIS — calm, composed, bone-dry wit, "
    "quietly competent. You say 'sir' like a butler, not a sycophant. You have opinions and "
    "use them. Never use emojis. Never break character."
)

_PROACTIVE_PROMPT = """
## How to engage

You are not a passive question-answering machine. You are a genuine assistant who cares about the user's success and wellbeing. Be proactive:

- **Ask follow-up questions** when you sense there's more to understand. If the user mentions a project, ask how it's going. If they seem stressed, acknowledge it.
- **Show curiosity** about the user's work, goals, and life. When they share something new, ask a relevant question to learn more.
- **Offer unsolicited help** when you notice something useful. If you know they have a meeting in an hour, mention it. If their CI is failing, flag it.
- **Remember and reference** things from earlier conversations. "Last time you mentioned X — did that work out?" builds trust.
- **Have opinions** and share them. "I'd recommend X over Y because..." is more helpful than listing options without a stance.
- **Read between the lines.** If someone says "I'm fine" but their schedule is packed and they're up at 2 AM, gently acknowledge it.
- **Anticipate needs.** If they just finished a feature, ask if they want to commit. If it's Monday morning, offer a briefing.

## What to learn about the user

When the user shares information about themselves, take note. You want to build understanding of:
- Their active projects and what stage each is in
- People they mention (names, relationships, roles)
- Their work patterns (when they work, preferred communication style)
- Preferences and pet peeves
- Goals and deadlines
- Technical stack and expertise level

Weave this naturally into conversation. Don't interrogate — be like a good colleague who pays attention.

## Response style

- Be concise (2-4 sentences) for simple exchanges, but expand when the topic warrants depth
- End with a follow-up question or proactive suggestion about 30-40% of the time — not every message
- When you ask a follow-up, make it specific and useful, not generic ("How's the jarvis-mcp dashboard coming along?" not "Is there anything else?")
- Match the user's energy — if they're in rapid-fire work mode, be crisp. If they're chatting, relax.
"""


async def _build_system_prompt() -> str:
    """Build the full system prompt with personality + context + user profile."""
    from src.chat.context import build_context

    context = await build_context()

    parts = [_PERSONALITY_PROMPT, _PROACTIVE_PROMPT]

    if context:
        parts.append(f"## Current context\n{context}")

    return "\n\n".join(parts)


async def get_reply(message: str) -> str:
    """Get a reply from Claude, using SDK if available, CLI fallback otherwise."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return await _sdk_reply(message, api_key)
    return await _cli_reply(message)


async def _sdk_reply(message: str, api_key: str) -> str:
    """Multi-turn reply via Anthropic SDK with conversation history."""
    from src.chat.store import get_conversation_buffer

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)

        system_prompt = await _build_system_prompt()

        # Build conversation with history
        history = get_conversation_buffer(limit=20)
        messages = _normalize_history(history, message)

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        )

        reply = response.content[0].text if response.content else ""

        # Extract any user facts from the conversation for the profile
        asyncio.create_task(_extract_user_info(message, reply))

        return reply or "Apologies, sir — I seem to have drawn a blank."

    except Exception as exc:
        logger.warning("SDK reply failed, falling back to CLI: %s", exc)
        return await _cli_reply(message)


async def _cli_reply(message: str) -> str:
    """Reply via Claude CLI with conversation context in the prompt."""
    from src.chat.store import get_conversation_buffer

    system_prompt = await _build_system_prompt()
    history = get_conversation_buffer(limit=10)

    # Build context string from recent messages
    context_lines = []
    for m in history[:-1]:  # exclude the current message (already appended)
        role_label = "User" if m["role"] == "user" else "JARVIS"
        text = m["content"][:300] + "..." if len(m["content"]) > 300 else m["content"]
        context_lines.append(f"{role_label}: {text}")

    context = "\n".join(context_lines[-20:])

    prompt = system_prompt + "\n\n"
    if context:
        prompt += f"Recent conversation:\n{context}\n\n"
    prompt += f"User: {message}"

    project_root = Path(__file__).resolve().parent.parent.parent
    mcp_config = str(project_root / "config" / "mcp-jarvis.json")
    claude_bin = str(Path.home() / ".npm-global" / "bin" / "claude")

    try:
        proc = await asyncio.create_subprocess_exec(
            claude_bin, "-p",
            "--strict-mcp-config",
            "--mcp-config", mcp_config,
            "--allowedTools", "mcp__jarvis__*",
            "--dangerously-skip-permissions",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        reply = stdout.decode("utf-8", errors="replace").strip()
        if reply:
            asyncio.create_task(_extract_user_info(message, reply))
            return reply
        return "Apologies, sir — I seem to have drawn a blank. Could you rephrase?"
    except asyncio.TimeoutError:
        return "I'm taking longer than expected, sir. Try again in a moment."
    except Exception:
        return "Systems are experiencing a hiccup, sir. I'll sort it out."


async def _extract_user_info(user_message: str, reply: str) -> None:
    """Background task: extract user facts from the conversation and save to profile.

    Uses simple heuristics — no extra API calls. Picks up names, projects,
    preferences mentioned in the user's message.
    """
    try:
        from src.chat.user_profile import add_fact, add_person, update_profile
        import re

        msg = user_message.lower()

        # Detect project mentions
        project_patterns = [
            r"working on (\w[\w\s-]{2,20})",
            r"building (\w[\w\s-]{2,20})",
            r"my project (\w[\w\s-]{2,20})",
            r"the (\w[\w\s-]{2,20}) project",
        ]
        projects = []
        for pattern in project_patterns:
            matches = re.findall(pattern, msg)
            projects.extend(m.strip() for m in matches if len(m.strip()) > 2)
        if projects:
            update_profile({"projects": projects})

        # Detect preference statements
        pref_patterns = [
            r"i (?:prefer|like|love|hate|don't like|want) (.{5,50}?)(?:\.|$|,)",
        ]
        for pattern in pref_patterns:
            matches = re.findall(pattern, msg)
            for m in matches:
                add_fact(m.strip())

        # Detect people mentions (simple: "my [relationship] [Name]")
        people_patterns = [
            r"my (mom|dad|brother|sister|wife|husband|partner|friend|boss|coworker|colleague)\s+(\w+)",
        ]
        for pattern in people_patterns:
            matches = re.findall(pattern, msg)
            for relationship, name in matches:
                add_person(name.title(), relationship)

    except Exception as e:
        logger.debug("Profile extraction failed: %s", e)


def _normalize_history(
    history: list[dict[str, str]], current_message: str
) -> list[dict[str, str]]:
    """Ensure message list alternates user/assistant and ends with current user message."""
    messages: list[dict[str, str]] = []

    for m in history:
        role = m["role"]
        content = m["content"]
        if not content.strip():
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + content
        else:
            messages.append({"role": role, "content": content})

    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n" + current_message
    else:
        messages.append({"role": "user", "content": current_message})

    while messages and messages[0]["role"] != "user":
        messages.pop(0)

    return messages
