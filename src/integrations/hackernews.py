"""Real Hacker News API integration."""

from __future__ import annotations

import asyncio

import httpx

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


async def _fetch_story(
    story_id: int,
    client: httpx.AsyncClient,
) -> dict | None:
    """Fetch a single HN story by ID."""
    try:
        resp = await client.get(HN_ITEM_URL.format(id=story_id))
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def fetch_top_stories(
    limit: int = 10,
    min_score: int = 100,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Fetch top HN stories filtered by minimum score.

    Fetches story IDs, then story details in batches of 30.
    Returns list of dicts with: title, url, score, comments, author, hn_url.
    """
    _client = client or httpx.AsyncClient(timeout=10.0)
    own_client = client is None
    try:
        resp = await _client.get(HN_TOP_URL)
        resp.raise_for_status()
        story_ids: list[int] = resp.json()

        # Fetch details in batches of 30
        stories: list[dict] = []
        batch_size = 30
        for i in range(0, len(story_ids), batch_size):
            batch = story_ids[i : i + batch_size]
            tasks = [_fetch_story(sid, _client) for sid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, dict) and r.get("score", 0) >= min_score:
                    stories.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "score": r.get("score", 0),
                        "comments": r.get("descendants", 0),
                        "author": r.get("by", ""),
                        "hn_url": f"https://news.ycombinator.com/item?id={r.get('id', '')}",
                    })

            if len(stories) >= limit:
                break

        return stories[:limit]
    finally:
        if own_client:
            await _client.aclose()
