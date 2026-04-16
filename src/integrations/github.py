"""Real GitHub API integration via gh CLI with httpx fallback."""

from __future__ import annotations

import asyncio
import json

import httpx

GITHUB_API = "https://api.github.com"


async def _run_gh(args: list[str]) -> tuple[int, str]:
    """Run a ``gh`` CLI command and return (returncode, stdout)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "gh",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        return proc.returncode or 0, stdout.decode()
    except Exception:
        return 1, ""


async def fetch_repo_activity(
    repo: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch recent activity for a GitHub repo.

    Tries ``gh`` CLI first, falls back to httpx.
    Returns: {open_issues, recent_prs, ci_status}.
    """
    # Try gh CLI first
    rc, out = await _run_gh(["api", f"repos/{repo}/issues", "--paginate", "-q",
                             ".[0:5]", "--method", "GET"])
    if rc == 0 and out.strip():
        try:
            raw_issues = json.loads(out)
        except json.JSONDecodeError:
            raw_issues = None
    else:
        raw_issues = None

    # Fallback to httpx
    if raw_issues is None:
        _client = client or httpx.AsyncClient(timeout=10.0)
        own_client = client is None
        try:
            resp = await _client.get(
                f"{GITHUB_API}/repos/{repo}/issues",
                params={"state": "open", "per_page": 5},
            )
            resp.raise_for_status()
            raw_issues = resp.json()
        except Exception:
            raw_issues = []
        finally:
            if own_client:
                await _client.aclose()

    open_issues: list[dict] = []
    recent_prs: list[dict] = []

    for item in raw_issues or []:
        entry = {
            "title": item.get("title", ""),
            "url": item.get("html_url", ""),
            "number": item.get("number", 0),
            "user": item.get("user", {}).get("login", ""),
        }
        if item.get("pull_request"):
            recent_prs.append(entry)
        else:
            open_issues.append(entry)

    ci_status = await check_ci_status(repo)

    return {
        "open_issues": open_issues,
        "recent_prs": recent_prs,
        "ci_status": ci_status,
    }


async def fetch_user_repos(limit: int = 10) -> list[str]:
    """Fetch user's repos via ``gh repo list``.

    Returns list of ``owner/repo`` strings.
    """
    rc, out = await _run_gh([
        "repo", "list", "--limit", str(limit), "--json", "nameWithOwner",
    ])
    if rc != 0 or not out.strip():
        return []
    try:
        repos = json.loads(out)
        return [r["nameWithOwner"] for r in repos]
    except (json.JSONDecodeError, KeyError):
        return []


async def check_ci_status(repo: str) -> str | None:
    """Check the latest CI run status for a repo.

    Returns ``"passing"``, ``"failing"``, ``"pending"``, or ``None``.
    """
    rc, out = await _run_gh([
        "run", "list", "--repo", repo, "--limit", "1",
        "--json", "status,conclusion",
    ])
    if rc != 0 or not out.strip():
        return None
    try:
        runs = json.loads(out)
        if not runs:
            return None
        run = runs[0]
        status = run.get("status", "")
        conclusion = run.get("conclusion", "")
        if status == "completed":
            return "passing" if conclusion == "success" else "failing"
        return "pending"
    except (json.JSONDecodeError, KeyError):
        return None
