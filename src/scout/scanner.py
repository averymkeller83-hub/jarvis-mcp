"""Source scanning — live API integrations for Scout discovery."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.scout.sources import ScoutSource


def _get_github_token() -> str | None:
    """Pull GitHub token from gh CLI keyring (no secrets in code)."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _github_headers() -> dict[str, str]:
    """Build GitHub API headers, with auth if available."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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
    """Scan Anthropic SDK releases for new capabilities/API changes."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/repos/anthropics/anthropic-sdk-python/releases",
                params={"per_page": 5},
                headers=_github_headers(),
            )
            resp.raise_for_status()
            candidates: list[Candidate] = []
            for release in resp.json()[:3]:
                tag = release.get("tag_name", "")
                body = release.get("body", "") or ""
                # Extract meaningful lines from release notes
                lines = [l.strip() for l in body.split("\n") if l.strip() and not l.startswith("Full Changelog")]
                pitch = " ".join(lines[:3])[:200] or f"Anthropic SDK {tag} release"
                candidates.append(Candidate(
                    id=_uid(),
                    name=f"Anthropic SDK {tag}",
                    pitch=pitch,
                    source="anthropic_changelog",
                    source_url=release.get("html_url", ""),
                    candidate_type="changelog",
                    metadata={"tag": tag, "published": release.get("published_at", "")},
                ))
            return candidates
    except Exception:
        return []


async def scan_mcp_registry(urls: list[str]) -> list[Candidate]:
    """Scan MCP registries (npm, GitHub) for new/popular MCP servers."""
    import httpx
    from datetime import timedelta

    candidates: list[Candidate] = []
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Search GitHub for recently updated MCP servers
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"mcp-server in:name pushed:>{since}",
                    "sort": "updated",
                    "per_page": 5,
                },
                headers=_github_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                for repo in data.get("items", []):
                    candidates.append(Candidate(
                        id=_uid(),
                        name=repo["name"],
                        pitch=repo.get("description", "")[:200] or f"MCP server — {repo['stargazers_count']} stars",
                        source="mcp_registry",
                        source_url=repo["html_url"],
                        candidate_type="mcp_server",
                        metadata={
                            "stars": repo.get("stargazers_count", 0),
                            "language": repo.get("language", ""),
                            "updated": repo.get("updated_at", ""),
                        },
                    ))
    except Exception:
        pass
    return candidates


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
                for pr in activity.get("recent_prs", []):
                    candidates.append(Candidate(
                        id=_uid(),
                        name=f"PR #{pr.get('number', '?')}: {pr.get('title', '')}",
                        pitch=f"Open PR in {repo} by {pr.get('user', 'unknown')}",
                        source="github_repos",
                        source_url=pr.get("url", ""),
                        candidate_type="github_issue",
                        metadata={"repo": repo, "type": "pr"},
                    ))
                ci = activity.get("ci_status")
                if ci == "failing":
                    candidates.append(Candidate(
                        id=_uid(),
                        name=f"CI failing: {repo}",
                        pitch=f"Latest CI run is failing in {repo} — needs attention",
                        source="github_repos",
                        source_url=f"https://github.com/{repo}/actions",
                        candidate_type="github_issue",
                        metadata={"repo": repo, "type": "ci_failure"},
                    ))
            except Exception:
                continue
        return candidates
    except Exception:
        return []


async def scan_github_trending(languages: list[str]) -> list[Candidate]:
    """Scan GitHub trending repos via search API (sorted by stars, recently created)."""
    import httpx
    from datetime import timedelta

    candidates: list[Candidate] = []
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            lang_filter = f" language:{languages[0]}" if languages else ""
            min_stars = 10 if languages else 50
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"created:>{since}{lang_filter} stars:>{min_stars}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 5,
                },
                headers=_github_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                for repo in data.get("items", []):
                    candidates.append(Candidate(
                        id=_uid(),
                        name=repo["full_name"],
                        pitch=repo.get("description", "")[:200] or f"Trending — {repo['stargazers_count']} stars this week",
                        source="github_trending",
                        source_url=repo["html_url"],
                        candidate_type="cli",
                        metadata={
                            "language": repo.get("language", ""),
                            "stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "created": repo.get("created_at", ""),
                        },
                    ))
    except Exception:
        pass
    return candidates


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
        return candidates
    except Exception:
        return []


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
        return candidates
    except Exception:
        return []


async def scan_source(source: ScoutSource) -> ScanResult:
    """Dispatch to the right scanner based on source name."""
    try:
        candidates: list[Candidate] = []

        if source.name == "anthropic_changelog":
            candidates = await scan_anthropic_changelog()
        elif source.name == "claude_plugin_marketplace":
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
