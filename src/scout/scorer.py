"""Relevance scoring for Scout candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.scout.scanner import Candidate

# Keywords that boost scores when found in name/pitch
_STACK_KEYWORDS = {
    "python", "fastapi", "mcp", "claude", "sqlite", "ai", "agent",
    "typescript", "react", "node", "rust", "go",
}

_EXECUTABLE_TYPES = {"mcp_server", "plugin", "cli"}
_INFO_TYPES = {"rss_item", "changelog", "github_issue"}


@dataclass
class ScoredCandidate:
    """A candidate with relevance scoring attached."""

    candidate: Candidate
    relevance_score: float  # 0.0 — 1.0
    match_reasons: list[str] = field(default_factory=list)
    sandbox_required: bool = False


def score_candidate(
    candidate: Candidate,
    user_context: dict | None = None,
) -> ScoredCandidate:
    """Score a single candidate for relevance.

    Args:
        candidate: The candidate to score.
        user_context: Optional dict with keys like stack, projects, recent_topics.

    Returns:
        A ScoredCandidate with score in [0.0, 1.0].
    """
    ctx = user_context or {}
    score = 0.0
    reasons: list[str] = []

    # ── Base score by type ──────────────────────────────────────────
    if candidate.candidate_type in _EXECUTABLE_TYPES:
        score = 0.5
        reasons.append(f"executable type ({candidate.candidate_type})")
        sandbox_required = True
    else:
        score = 0.3
        reasons.append(f"informational type ({candidate.candidate_type})")
        sandbox_required = False

    # ── Keyword match against name + pitch ──────────────────────────
    text = f"{candidate.name} {candidate.pitch}".lower()

    user_stack = [s.lower() for s in ctx.get("stack", [])]
    if user_stack:
        for kw in user_stack:
            if kw in text:
                score += 0.15
                reasons.append(f"matches your {kw} stack")
                break  # one stack bump is enough
    else:
        # Fallback: check against default keywords
        for kw in _STACK_KEYWORDS:
            if kw in text:
                score += 0.1
                reasons.append(f"keyword match: {kw}")
                break

    # ── Project relevance ───────────────────────────────────────────
    user_projects = [p.lower() for p in ctx.get("projects", [])]
    for proj in user_projects:
        if proj in text:
            score += 0.1
            reasons.append(f"relates to your project: {proj}")
            break

    # ── Topic relevance ─────────────────────────────────────────────
    recent_topics = [t.lower() for t in ctx.get("recent_topics", [])]
    for topic in recent_topics:
        if topic in text:
            score += 0.1
            reasons.append(f"matches recent topic: {topic}")
            break

    # ── Source quality bonus ─────────────────────────────────────────
    if candidate.source in ("anthropic_changelog", "mcp_registry"):
        score += 0.05
        reasons.append("from a high-quality source")

    # Clamp to [0.0, 1.0]
    score = round(min(max(score, 0.0), 1.0), 4)

    return ScoredCandidate(
        candidate=candidate,
        relevance_score=score,
        match_reasons=reasons,
        sandbox_required=sandbox_required,
    )


def rank_candidates(
    candidates: list[ScoredCandidate],
    limit: int = 3,
) -> list[ScoredCandidate]:
    """Sort by relevance score descending, return top N."""
    sorted_list = sorted(candidates, key=lambda sc: sc.relevance_score, reverse=True)
    return sorted_list[:limit]
