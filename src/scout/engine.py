"""Main Scout orchestration — ties scanning, scoring, sandbox, and cards together."""

from __future__ import annotations

from src.scout.cards import ScoutCard, build_card, card_to_dict
from src.scout.sandbox import SandboxResult, sandbox_test
from src.scout.scanner import Candidate, ScanResult, scan_source
from src.scout.scorer import ScoredCandidate, rank_candidates, score_candidate
from src.scout.sources import ScoutSource, get_enabled_sources


async def run_discovery(
    sources: list[ScoutSource] | None = None,
    user_context: dict | None = None,
) -> list[ScoutCard]:
    """Full discovery pipeline: scan -> score -> sandbox -> cards.

    Args:
        sources: Explicit source list, or None to use enabled sources from config.
        user_context: Optional dict with stack/projects/recent_topics for scoring.

    Returns:
        List of ScoutCards sorted by relevance, top candidates first.
    """
    if sources is None:
        sources = get_enabled_sources()

    # 1. Scan every source
    scan_results: list[ScanResult] = []
    for src in sources:
        result = await scan_source(src)
        scan_results.append(result)

    # 2. Collect all candidates
    all_candidates: list[Candidate] = []
    for sr in scan_results:
        all_candidates.extend(sr.candidates)

    if not all_candidates:
        return []

    # 3. Score every candidate
    scored: list[ScoredCandidate] = [
        score_candidate(c, user_context) for c in all_candidates
    ]

    # 4. Rank and keep top results
    top = rank_candidates(scored, limit=10)

    # 5. Sandbox-test executable candidates
    sandbox_results: dict[str, SandboxResult] = {}
    for sc in top:
        sb = await sandbox_test(sc.candidate)
        sandbox_results[sc.candidate.id] = sb

    # 6. Build cards
    cards: list[ScoutCard] = []
    for sc in top:
        sb = sandbox_results.get(sc.candidate.id)
        card = build_card(sc, sb)
        cards.append(card)

    return cards


async def install_candidate(
    candidate_id: str,
    candidates: dict[str, Candidate],
) -> dict:
    """Bookmark a candidate for installation.

    Logs the action and returns the source URL for the user to review.
    """
    candidate = candidates.get(candidate_id)
    if candidate is None:
        return {
            "status": "error",
            "message": f"Candidate {candidate_id} not found",
        }

    import logging
    logging.getLogger(__name__).info(
        "Candidate bookmarked: %s (%s)", candidate.name, candidate.source_url
    )

    return {
        "status": "installed",
        "candidate_id": candidate_id,
        "name": candidate.name,
        "source_url": candidate.source_url or "",
        "message": f"Bookmarked {candidate.name} — source: {candidate.source_url or 'N/A'}",
    }
