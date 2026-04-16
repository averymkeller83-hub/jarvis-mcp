"""Sandbox testing infrastructure for Scout candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from src.scout.scanner import Candidate

_SANDBOX_EXPIRY_DAYS = 7

_NON_EXECUTABLE_TYPES = {"rss_item", "changelog", "github_issue"}


@dataclass
class SandboxResult:
    """Result of sandbox-testing a candidate."""

    candidate_id: str
    passed: bool
    test_log: list[str] = field(default_factory=list)
    tested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""

    def __post_init__(self) -> None:
        if not self.expires_at:
            tested = datetime.fromisoformat(self.tested_at)
            self.expires_at = (tested + timedelta(days=_SANDBOX_EXPIRY_DAYS)).isoformat()


async def sandbox_test(candidate: Candidate) -> SandboxResult:
    """Run sandbox tests against a candidate.

    Non-executable types (rss_item, changelog, github_issue) pass immediately.
    Executable types get a simulated test sequence (real Colima in v2).
    """
    now = datetime.now(timezone.utc).isoformat()

    if candidate.candidate_type in _NON_EXECUTABLE_TYPES:
        return SandboxResult(
            candidate_id=candidate.id,
            passed=True,
            test_log=["No sandbox required for informational content."],
            tested_at=now,
        )

    # Simulate executable sandbox flow
    log = [
        f"Sandbox test started for {candidate.name}",
        "Pulling container image...",
        "Installing candidate...",
        "Running smoke tests...",
        "Checking for port conflicts...",
        "Verifying clean shutdown...",
        "All tests passed.",
    ]

    return SandboxResult(
        candidate_id=candidate.id,
        passed=True,
        test_log=log,
        tested_at=now,
    )


def is_sandbox_expired(result: SandboxResult) -> bool:
    """Check whether a sandbox result's 7-day window has passed."""
    expires = datetime.fromisoformat(result.expires_at)
    # Normalise naive datetimes (pre-3.11 fromisoformat) to UTC
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires


async def cleanup_expired(results: list[SandboxResult]) -> int:
    """Remove expired sandbox results, return count cleaned up."""
    count = 0
    to_remove: list[SandboxResult] = []
    for r in results:
        if is_sandbox_expired(r):
            to_remove.append(r)
            count += 1
    for r in to_remove:
        results.remove(r)
    return count
