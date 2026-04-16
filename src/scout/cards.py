"""Scout card generation for display in briefings, Telegram, and API."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.scout.sandbox import SandboxResult
from src.scout.scorer import ScoredCandidate


@dataclass
class ScoutCard:
    """A presentation-ready card for a Scout discovery."""

    candidate_id: str
    name: str
    pitch: str
    source_badge: str
    match_reason: str
    sandbox_status: str  # "passed" | "pending" | "not_required" | "failed"
    install_available: bool
    details: dict = field(default_factory=dict)


def _sandbox_status(scored: ScoredCandidate, sandbox: SandboxResult | None) -> str:
    if not scored.sandbox_required:
        return "not_required"
    if sandbox is None:
        return "pending"
    return "passed" if sandbox.passed else "failed"


def build_card(scored: ScoredCandidate, sandbox: SandboxResult | None = None) -> ScoutCard:
    """Build a ScoutCard from a scored candidate and optional sandbox result."""
    status = _sandbox_status(scored, sandbox)
    install_ok = status in ("passed", "not_required")

    return ScoutCard(
        candidate_id=scored.candidate.id,
        name=scored.candidate.name,
        pitch=scored.candidate.pitch,
        source_badge=scored.candidate.source,
        match_reason="; ".join(scored.match_reasons) if scored.match_reasons else "general match",
        sandbox_status=status,
        install_available=install_ok,
        details={
            "relevance_score": scored.relevance_score,
            "candidate_type": scored.candidate.candidate_type,
            "source_url": scored.candidate.source_url,
            "metadata": scored.candidate.metadata,
        },
    )


def card_to_markdown(card: ScoutCard) -> str:
    """Render a ScoutCard as compact Markdown for briefings/Telegram."""
    lines = [
        f"**{card.name}** `[{card.source_badge}]`",
        f"> {card.pitch}",
        f"Match: {card.match_reason}",
        f"Sandbox: {card.sandbox_status}",
    ]
    if card.install_available:
        lines.append("Install: ready")
    return "\n".join(lines)


def card_to_dict(card: ScoutCard) -> dict:
    """Render a ScoutCard as a JSON-serializable dict for the API."""
    return {
        "candidate_id": card.candidate_id,
        "name": card.name,
        "pitch": card.pitch,
        "source_badge": card.source_badge,
        "match_reason": card.match_reason,
        "sandbox_status": card.sandbox_status,
        "install_available": card.install_available,
        "details": card.details,
    }
