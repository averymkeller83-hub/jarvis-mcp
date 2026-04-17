"""Build the user_context dict that Scout's scorer expects, using the dynamic user profile."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Baseline stack items — always included so Scout has something to work with
# even when the profile is empty.
_DEFAULT_STACK = [
    "python", "fastapi", "react", "typescript", "mcp", "claude", "ai", "agent",
]

_DEFAULT_PROJECTS = [
    "jarvis", "magic-puffs", "clawwork", "sakura-radio", "chess-agent",
]

_DEFAULT_TOPICS = [
    "mcp", "dashboard", "scout", "voice", "tts", "integration",
]


def build_user_context() -> dict:
    """Return a ``user_context`` dict for :func:`run_discovery`.

    Reads the dynamic user profile and maps its fields to the format
    Scout's scorer expects (``stack``, ``projects``, ``recent_topics``).
    Falls back to sensible defaults when the profile is empty, and
    augments the defaults with any profile data that exists.
    """
    try:
        from src.chat.user_profile import get_profile
        profile = get_profile()
    except Exception:
        logger.debug("Could not load user profile; using defaults", exc_info=True)
        profile = {}

    # --- stack ---
    # Profile "interests" map naturally to stack/technology keywords.
    # Profile "preferences" keys can also hint at stack items.
    stack: list[str] = list(_DEFAULT_STACK)
    for interest in profile.get("interests", []):
        token = interest.lower().strip()
        if token and token not in stack:
            stack.append(token)

    # --- projects ---
    projects: list[str] = list(_DEFAULT_PROJECTS)
    for proj in profile.get("projects", []):
        token = proj.lower().strip()
        if token and token not in projects:
            projects.append(token)

    # --- recent_topics ---
    # Profile "facts" often contain recently discussed topics/context.
    # We pull the last few as topic signals.
    topics: list[str] = list(_DEFAULT_TOPICS)
    for fact in profile.get("facts", [])[-10:]:
        # Extract short keywords from facts (take first two words as a heuristic)
        words = fact.lower().split()[:3]
        for w in words:
            cleaned = w.strip(".,;:!?()\"'")
            if len(cleaned) > 2 and cleaned not in topics:
                topics.append(cleaned)

    return {
        "stack": stack,
        "projects": projects,
        "recent_topics": topics,
    }
