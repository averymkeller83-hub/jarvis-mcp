"""Smart router — classifies every user message and routes it to the right surface."""

from __future__ import annotations

import re
from enum import Enum

# ---------------------------------------------------------------------------
# Surface enum
# ---------------------------------------------------------------------------

class Surface(str, Enum):
    CHAT = "chat"
    REASON = "reason"
    CODE = "code"
    DESKTOP = "desktop"
    LOCAL = "local"
    CONTROL = "control"


# ---------------------------------------------------------------------------
# Pattern banks — regex fast-path before Haiku fallback
# ---------------------------------------------------------------------------

_CONTROL_PATTERNS: list[str] = [
    # Messaging
    r"(?:^|\s)(?:text|message)\s+(?!me\b)\w+",
    r"\bsend\s+(?:a\s+)?(?:text|message)\s+(?:to\s+)?\w+",
    r"\b(?:imessage|sms)\s+\w+",
    r"\btell\s+\w+\s+(?:that|to)\b",
    # Reminders
    r"\bremind\s+me\b",
    r"\badd\s+.+?\s+to\s+(?:my\s+)?(?:\w+\s+)?list\b",
    r"\bset\s+(?:a\s+)?reminder\b",
    # Alarms & timers
    r"\bset\s+(?:an?\s+)?alarm\b",
    r"\bset\s+(?:a\s+)?timer\b",
    r"\bwake\s+me\b",
    r"\bsnooze\b",
    r"\bstop\s+(?:the\s+)?alarm\b",
    r"\bcancel\s+(?:the\s+)?(?:alarm|timer)\b",
    # Music
    r"\b(?:play|queue)\s+.+",
    r"\b(?:pause|resume|skip|next\s+(?:track|song)|previous\s+(?:track|song))\b",
    r"\b(?:set\s+)?volume\s+(?:to\s+)?\d+",
    r"\b(?:turn\s+(?:up|down)\s+(?:the\s+)?(?:volume|music))\b",
    r"\bshuffle\b",
    # HomeKit
    r"\bturn\s+(?:on|off)\s+(?:the\s+)?\w+",
    r"\bset\s+(?:the\s+)?thermostat\b",
    r"\b(?:good\s+(?:night|morning|evening))\b",
    r"\block\s+(?:the\s+)?\w+",
    r"\bunlock\s+(?:the\s+)?\w+",
    r"\bdim\s+(?:the\s+)?\w+",
    # Calls
    r"\bcall\s+\w+",
    r"\bfacetime\s+\w+",
    r"\bdial\s+\w+",
    r"\bhang\s+up\b",
    # Calendar (short commands)
    r"\badd\s+(?:an?\s+)?event\b",
    r"\bschedule\s+(?:a\s+)?(?:meeting|call|event)\b",
    r"\bwhat(?:'s|s|\s+is)\s+(?:on\s+)?(?:my\s+)?(?:calendar|schedule)\s+(?:at|for|on|today|tomorrow)\b",
]

_LOCAL_PATTERNS: list[str] = [
    r"\bbriefing\b",
    r"\b(?:my\s+)?schedule\b",
    r"\b(?:my\s+)?calendar\b",
    r"\b(?:my\s+)?tasks?\b",
    r"\b(?:my\s+)?queue\b",
    r"\bunread\b",
    r"\bweather\b",
    r"\bheadlines\b",
    r"\bstatus\b",
    r"\bpatterns?\b",
    r"\blessons?\b",
    r"\bwhat(?:'s|s)?\s+(?:on\s+)?(?:my\s+)?(?:plate|agenda)\b",
    r"\bgood\s+morning\s+jarvis\b",
]

_CODE_PATTERNS: list[str] = [
    r"\b(?:write|create|build|implement|scaffold)\s+(?:a\s+|the\s+)?(?:function|class|module|component|endpoint|api|script|test)\b",
    r"\b(?:fix|debug|patch|troubleshoot)\s+(?:the\s+|this\s+|a\s+)?(?:bug|error|issue|crash|code)\b",
    r"\brefactor\b",
    r"\b(?:code\s+review|review\s+(?:the\s+|this\s+)?code)\b",
    r"\b(?:pull\s+request|merge\s+request|PR)\b",
    r"\b(?:git\s+\w+|commit|push|pull|rebase|cherry.pick|stash)\b",
    r"\b(?:run|write|add)\s+(?:the\s+)?tests?\b",
    r"\b(?:npm|pip|cargo|yarn|pnpm|poetry|pdm)\s+\w+",
    r"\b(?:deploy|ci|cd|pipeline|dockerfile|docker.compose)\b",
    r"\blint\b",
    r"\b(?:type.?check|mypy|pyright|tsc)\b",
]

_DESKTOP_PATTERNS: list[str] = [
    r"\bclick\s+(?:on\s+)?(?:the\s+)?\w+",
    r"\btap\s+(?:on\s+)?(?:the\s+)?\w+",
    r"\bscreenshot\b",
    r"\bopen\s+(?:the\s+)?(?:app\s+)?\w+",
    r"\bclose\s+(?:the\s+)?(?:app\s+)?\w+",
    r"\bnavigate\s+to\b",
    r"\bautomate\b",
    r"\bdrag\s+(?:and\s+)?drop\b",
    r"\bswitch\s+(?:to\s+)?(?:the\s+)?\w+\s+(?:window|app|tab)\b",
    r"\bminimize\b",
    r"\bmaximize\b",
    r"\bresize\s+(?:the\s+)?window\b",
    r"\btype\s+(?:in\s+)?(?:the\s+)?.+\s+field\b",
    r"\bscroll\s+(?:up|down)\b",
    r"\bmove\s+(?:the\s+)?(?:mouse|cursor)\b",
]

_REASON_PATTERNS: list[str] = [
    r"\banalyze\b",
    r"\bresearch\b",
    r"\bexplain\s+(?:in\s+)?(?:depth|detail)\b",
    r"\bwrite\s+(?:a\s+|an\s+)?(?:essay|article|report|paper|memo|brief)\b",
    r"\bcompare\s+(?:and\s+contrast\s+)?\w+",
    r"\bpros\s+and\s+cons\b",
    r"\bdeep\s+dive\b",
    r"\bbreak\s*down\b",
    r"\bevaluate\b",
    r"\bsummarize\s+(?:the\s+|this\s+)?\w+",
    r"\bwhat\s+are\s+the\s+(?:implications|tradeoffs|trade.offs|consequences)\b",
    r"\bthink\s+(?:through|about\s+this\s+carefully)\b",
    r"\bstep\s+by\s+step\b",
    r"\bweigh\s+(?:the\s+)?(?:options|alternatives)\b",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches(text: str, patterns: list[str]) -> bool:
    """Return True if *text* matches any pattern in the list (case-insensitive)."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------

def classify(text: str) -> Surface:
    """Classify a user message into a routing surface.

    Check order: CONTROL > LOCAL > DESKTOP > CODE > REASON > CHAT (fallback).
    CONTROL is checked first so short imperative phrases like "text Mom"
    don't fall through to CHAT.
    """
    cleaned = text.strip()
    if not cleaned:
        return Surface.CHAT

    if _matches(cleaned, _CONTROL_PATTERNS):
        return Surface.CONTROL
    if _matches(cleaned, _LOCAL_PATTERNS):
        return Surface.LOCAL
    if _matches(cleaned, _DESKTOP_PATTERNS):
        return Surface.DESKTOP
    if _matches(cleaned, _CODE_PATTERNS):
        return Surface.CODE
    if _matches(cleaned, _REASON_PATTERNS):
        return Surface.REASON
    return Surface.CHAT


# ---------------------------------------------------------------------------
# control_intent  — structured extraction for CONTROL surface
# ---------------------------------------------------------------------------

_INTENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    # Messaging
    ("message", re.compile(
        r"\b(?:text|message|sms|imessage)\s+(?:to\s+)?(?P<target>\w+)"
        r"(?:\s+(?:saying|that|to\s+say)?\s*(?P<payload>.+))?$",
        re.IGNORECASE,
    )),
    ("message", re.compile(
        r"\bsend\s+(?:a\s+)?(?:text|message)\s+(?:to\s+)?(?P<target>\w+)"
        r"(?:\s+(?:saying|that)?\s*(?P<payload>.+))?$",
        re.IGNORECASE,
    )),
    ("message", re.compile(
        r"\btell\s+(?P<target>\w+)\s+(?:that|to)\s+(?P<payload>.+)$",
        re.IGNORECASE,
    )),
    # Reminders
    ("remind", re.compile(
        r"\bremind\s+me\s+(?:to\s+)?(?P<payload>.+?)(?:\s+(?:at|in|on|by|tomorrow|tonight)\s+(?P<target>.+))?$",
        re.IGNORECASE,
    )),
    ("remind", re.compile(
        r"\bset\s+(?:a\s+)?reminder\s+(?:to\s+)?(?P<payload>.+?)(?:\s+(?:at|in|on|by)\s+(?P<target>.+))?$",
        re.IGNORECASE,
    )),
    # List items
    ("add_to_list", re.compile(
        r"\badd\s+(?P<payload>.+?)\s+to\s+(?:my\s+)?(?P<target>\w+(?:\s+\w+)?)\s+list\b",
        re.IGNORECASE,
    )),
    # Alarms
    ("alarm", re.compile(
        r"\bset\s+(?:an?\s+)?alarm\s+(?:for\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("alarm", re.compile(
        r"\bwake\s+me\s+(?:up\s+)?(?:at|in)\s+(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("cancel_alarm", re.compile(
        r"\b(?:stop|cancel|snooze)\s+(?:the\s+)?(?:alarm|timer)\b",
        re.IGNORECASE,
    )),
    # Timers
    ("timer", re.compile(
        r"\bset\s+(?:a\s+)?timer\s+(?:for\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    # Music
    ("play", re.compile(
        r"\b(?:play|queue)\s+(?P<payload>.+)$",
        re.IGNORECASE,
    )),
    ("pause", re.compile(r"\b(?:pause|stop\s+(?:the\s+)?music)\b", re.IGNORECASE)),
    ("skip", re.compile(r"\b(?:skip|next\s+(?:track|song))\b", re.IGNORECASE)),
    ("previous", re.compile(r"\bprevious\s+(?:track|song)\b", re.IGNORECASE)),
    ("volume", re.compile(
        r"\b(?:set\s+)?volume\s+(?:to\s+)?(?P<target>\d+)",
        re.IGNORECASE,
    )),
    ("volume_up", re.compile(r"\bturn\s+up\s+(?:the\s+)?(?:volume|music)\b", re.IGNORECASE)),
    ("volume_down", re.compile(r"\bturn\s+down\s+(?:the\s+)?(?:volume|music)\b", re.IGNORECASE)),
    # HomeKit
    ("turn_on", re.compile(
        r"\bturn\s+on\s+(?:the\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("turn_off", re.compile(
        r"\bturn\s+off\s+(?:the\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("thermostat", re.compile(
        r"\bset\s+(?:the\s+)?thermostat\s+(?:to\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("scene", re.compile(
        r"\b(?P<payload>good\s+(?:night|morning|evening))\b",
        re.IGNORECASE,
    )),
    ("lock", re.compile(
        r"\block\s+(?:the\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    ("unlock", re.compile(
        r"\bunlock\s+(?:the\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    )),
    # Calls
    ("call", re.compile(
        r"\b(?:call|dial)\s+(?P<target>\w+(?:\s+\w+)?)\b",
        re.IGNORECASE,
    )),
    ("facetime", re.compile(
        r"\bfacetime\s+(?P<target>\w+(?:\s+\w+)?)\b",
        re.IGNORECASE,
    )),
    ("hang_up", re.compile(r"\bhang\s+up\b", re.IGNORECASE)),
    # Calendar
    ("add_event", re.compile(
        r"\b(?:add\s+(?:an?\s+)?event|schedule\s+(?:a\s+)?(?:meeting|call|event))\s+(?P<payload>.+)$",
        re.IGNORECASE,
    )),
    ("check_calendar", re.compile(
        r"\bwhat(?:'s|s|\s+is)\s+(?:on\s+)?(?:my\s+)?(?:calendar|schedule)\s+(?:at|for|on)\s+(?P<target>.+)$",
        re.IGNORECASE,
    )),
]


def control_intent(text: str) -> dict | None:
    """Extract a structured intent from a CONTROL-classified message.

    Returns ``{"verb": str, "target": str | None, "payload": str | None}``
    or ``None`` if no rule matched (caller should fall back to Haiku).
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    for verb, pattern in _INTENT_RULES:
        m = pattern.search(cleaned)
        if m:
            groups = m.groupdict()
            target = (groups.get("target") or "").strip() or None
            payload = (groups.get("payload") or "").strip() or None
            return {"verb": verb, "target": target, "payload": payload}
    return None


# ---------------------------------------------------------------------------
# local_intent  — map LOCAL messages to handler names
# ---------------------------------------------------------------------------

_LOCAL_HANDLER_MAP: list[tuple[str, str]] = [
    (r"\bbriefing\b", "briefing"),
    (r"\bgood\s+morning\s+jarvis\b", "briefing"),
    (r"\bwhat(?:'s|s)?\s+(?:on\s+)?(?:my\s+)?(?:plate|agenda)\b", "briefing"),
    (r"\b(?:my\s+)?tasks?\b", "tasks"),
    (r"\b(?:my\s+)?queue\b", "tasks"),
    (r"\b(?:my\s+)?schedule\b", "schedule"),
    (r"\b(?:my\s+)?calendar\b", "schedule"),
    (r"\bunread\b", "unread"),
    (r"\bweather\b", "weather"),
    (r"\bheadlines\b", "headlines"),
    (r"\bstatus\b", "status"),
    (r"\bpatterns?\b", "patterns"),
    (r"\blessons?\b", "lessons"),
]


def local_intent(text: str) -> str | None:
    """Map a LOCAL-classified message to a handler name.

    Possible return values: ``"briefing"``, ``"tasks"``, ``"schedule"``,
    ``"unread"``, ``"weather"``, ``"headlines"``, ``"status"``,
    ``"patterns"``, ``"lessons"``.
    Returns ``None`` if no mapping is found.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    for pat, handler in _LOCAL_HANDLER_MAP:
        if re.search(pat, cleaned, re.IGNORECASE):
            return handler
    return None
