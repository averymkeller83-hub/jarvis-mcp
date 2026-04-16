"""Correction detection heuristics — pattern-match user messages for implicit lessons."""

from __future__ import annotations

import re

CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"no,?\s+(don'?t|stop|that'?s wrong|not that|I said|I told you)", re.IGNORECASE),
    re.compile(r"you forgot", re.IGNORECASE),
    re.compile(r"that'?s not (right|correct|done|what I)", re.IGNORECASE),
    re.compile(r"you lied", re.IGNORECASE),
    re.compile(r"I already told you", re.IGNORECASE),
    re.compile(r"\bwrong\b", re.IGNORECASE),
    re.compile(r"try again", re.IGNORECASE),
    re.compile(r"that'?s not done", re.IGNORECASE),
    re.compile(r"you didn'?t (test|check|verify|actually)", re.IGNORECASE),
]

# keyword -> category mapping (checked in order, first match wins)
_CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (["test", "verify", "done", "check", "confirm", "lie", "lied"], "trust"),
    (["remember", "forgot", "memory", "context", "already told"], "memory"),
    (["code", "bug", "function", "error", "syntax", "variable", "import"], "code"),
    (["say", "tone", "rude", "verbose", "emoji", "format", "communicate"], "communication"),
]


def detect_correction(message: str) -> bool:
    """Return True if the message matches any known correction pattern."""
    return any(p.search(message) for p in CORRECTION_PATTERNS)


def categorize(text: str) -> str:
    """Return the best category for *text* based on keyword matching."""
    lower = text.lower()
    for keywords, category in _CATEGORY_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return category
    return "general"


def draft_lesson(correction_message: str, context: str = "") -> dict:
    """Produce a draft lesson structure from a correction message.

    Returns a dict ready for review/approval before being persisted.
    """
    category = categorize(correction_message + " " + context)

    parts = [f"Correction: {correction_message.strip()}"]
    if context:
        parts.append(f"Context: {context.strip()}")
    parts.append("Action: adjust behavior to avoid repeating this mistake.")
    content = " | ".join(parts)

    return {
        "content": content,
        "category": category,
        "source": "heuristic",
        "status": "pending_approval",
    }
