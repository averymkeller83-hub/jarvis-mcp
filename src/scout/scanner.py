"""Source scanning — stub implementations returning mock data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.scout.sources import ScoutSource


@dataclass
class Candidate:
    """A discovered candidate item."""

    id: str
    name: str
    pitch: str
    source: str
    source_url: str | None
    candidate_type: str  # "mcp_server"|"plugin"|"cli"|"rss_item"|"changelog"|"github_issue"
    metadata: dict = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ScanResult:
    """Result of scanning a single source."""

    source: str
    candidates: list[Candidate]
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None


def _uid() -> str:
    return uuid.uuid4().hex[:12]


async def scan_anthropic_changelog() -> list[Candidate]:
    """Mock: scan Anthropic's changelog for new capabilities."""
    return [
        Candidate(
            id=_uid(),
            name="Claude 4.5 Extended Thinking",
            pitch="New extended-thinking mode doubles complex-reasoning accuracy",
            source="anthropic_changelog",
            source_url="https://docs.anthropic.com/changelog",
            candidate_type="changelog",
            metadata={"version": "4.5", "date": "2026-04-15"},
        ),
    ]


async def scan_mcp_registry(urls: list[str]) -> list[Candidate]:
    """Mock: scan MCP registries for new servers."""
    return [
        Candidate(
            id=_uid(),
            name="mcp-sqlite-explorer",
            pitch="Browse and query SQLite databases directly from Claude",
            source="mcp_registry",
            source_url=urls[0] if urls else "https://mcp.so",
            candidate_type="mcp_server",
            metadata={"stars": 342, "registry": "mcp.so"},
        ),
    ]


async def scan_github_repos() -> list[Candidate]:
    """Scan user's GitHub repos for actionable items via real API."""
    try:
        from src.integrations.github import fetch_repo_activity, fetch_user_repos

        repos = await fetch_user_repos(limit=5)
        candidates: list[Candidate] = []
        for repo in repos:
            try:
                activity = await fetch_repo_activity(repo)
                for issue in activity.get("open_issues", []):
                    candidates.append(Candidate(
                        id=_uid(),
                        name=f"Issue #{issue.get('number', '?')}: {issue.get('title', '')}",
                        pitch=f"Open issue in {repo}",
                        source="github_repos",
                        source_url=issue.get("url", ""),
                        candidate_type="github_issue",
                        metadata={"repo": repo},
                    ))
            except Exception:
                continue
        return candidates if candidates else _mock_github_repos()
    except Exception:
        return _mock_github_repos()


def _mock_github_repos() -> list[Candidate]:
    """Fallback mock data for GitHub repos scanner."""
    return [
        Candidate(
            id=_uid(),
            name="Issue #47: Memory leak in worker pool",
            pitch="High-priority issue open 3 days with no assignee",
            source="github_repos",
            source_url="https://github.com/user/repo/issues/47",
            candidate_type="github_issue",
            metadata={"repo": "user/repo", "priority": "high"},
        ),
    ]


async def scan_github_trending(languages: list[str]) -> list[Candidate]:
    """Mock: scan GitHub trending for relevant projects."""
    lang_label = languages[0] if languages else "python"
    return [
        Candidate(
            id=_uid(),
            name="fast-agent",
            pitch=f"Trending {lang_label} framework for building AI agents — 1.2k stars today",
            source="github_trending",
            source_url="https://github.com/example/fast-agent",
            candidate_type="cli",
            metadata={"language": lang_label, "stars_today": 1200},
        ),
    ]


async def scan_rss(feeds: list[str]) -> list[Candidate]:
    """Scan RSS/Atom feeds for new articles via real HTTP."""
    try:
        from src.integrations.rss import fetch_multiple_feeds

        items = await fetch_multiple_feeds(feeds, limit_per_feed=5)
        candidates: list[Candidate] = []
        for item in items:
            candidates.append(Candidate(
                id=_uid(),
                name=item.get("title", "Untitled"),
                pitch=item.get("summary", "")[:200] or "New article",
                source="rss_curated",
                source_url=item.get("url", ""),
                candidate_type="rss_item",
                metadata={"feed": item.get("source", ""), "published": item.get("published", "")},
            ))
        return candidates if candidates else _mock_rss(feeds)
    except Exception:
        return _mock_rss(feeds)


def _mock_rss(feeds: list[str]) -> list[Candidate]:
    """Fallback mock data for RSS scanner."""
    return [
        Candidate(
            id=_uid(),
            name="Building MCP Servers in 10 Minutes",
            pitch="Simon Willison walks through a minimal MCP server with Python",
            source="rss_curated",
            source_url="https://simonwillison.net/2026/Apr/15/mcp-servers/",
            candidate_type="rss_item",
            metadata={"author": "Simon Willison", "feed": feeds[0] if feeds else ""},
        ),
    ]


async def scan_hackernews(min_score: int = 100) -> list[Candidate]:
    """Scan Hacker News for high-score posts via real API."""
    try:
        from src.integrations.hackernews import fetch_top_stories

        stories = await fetch_top_stories(limit=10, min_score=min_score)
        candidates: list[Candidate] = []
        for story in stories:
            candidates.append(Candidate(
                id=_uid(),
                name=story.get("title", "Untitled"),
                pitch=f"HN post with {story.get('score', 0)} points",
                source="hackernews",
                source_url=story.get("hn_url", ""),
                candidate_type="rss_item",
                metadata={
                    "score": story.get("score", 0),
                    "comments": story.get("comments", 0),
                },
            ))
        return candidates if candidates else _mock_hackernews(min_score)
    except Exception:
        return _mock_hackernews(min_score)


def _mock_hackernews(min_score: int = 100) -> list[Candidate]:
    """Fallback mock data for HN scanner."""
    return [
        Candidate(
            id=_uid(),
            name="Show HN: Open-source Claude Code alternative",
            pitch=f"HN post with {min_score + 50} points — open-source CLI agent toolkit",
            source="hackernews",
            source_url="https://news.ycombinator.com/item?id=99999",
            candidate_type="rss_item",
            metadata={"score": min_score + 50, "comments": 87},
        ),
    ]


async def scan_source(source: ScoutSource) -> ScanResult:
    """Dispatch to the right scanner based on source name."""
    try:
        candidates: list[Candidate] = []

        if source.name == "anthropic_changelog":
            candidates = await scan_anthropic_changelog()
        elif source.name == "claude_plugin_marketplace":
            # Stub — no mock data yet for this source
            candidates = []
        elif source.name == "mcp_registry":
            candidates = await scan_mcp_registry(source.urls)
        elif source.name == "github_repos":
            candidates = await scan_github_repos()
        elif source.name == "github_trending":
            languages = source.config.get("languages", [])
            candidates = await scan_github_trending(languages)
        elif source.name in ("rss_curated", "custom_rss"):
            candidates = await scan_rss(source.urls)
        elif source.name == "hackernews":
            min_score = source.config.get("min_score", 100)
            candidates = await scan_hackernews(min_score)
        else:
            return ScanResult(
                source=source.name,
                candidates=[],
                error=f"Unknown source: {source.name}",
            )

        return ScanResult(source=source.name, candidates=candidates)

    except Exception as exc:
        return ScanResult(
            source=source.name,
            candidates=[],
            error=str(exc),
        )
