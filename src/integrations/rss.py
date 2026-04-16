"""Real RSS/Atom feed parsing via httpx + stdlib xml."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET

import httpx

# Atom namespace
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _parse_rss_items(root: ET.Element, limit: int, source: str) -> list[dict]:
    """Parse RSS 2.0 <item> elements."""
    items: list[dict] = []
    channel = root.find("channel")
    if channel is None:
        return items
    for item in channel.findall("item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        items.append({
            "title": title,
            "url": link,
            "summary": desc[:300],
            "published": pub,
            "source": source,
        })
    return items


def _parse_atom_entries(root: ET.Element, limit: int, source: str) -> list[dict]:
    """Parse Atom <entry> elements."""
    items: list[dict] = []
    for entry in root.findall(f"{_ATOM_NS}entry")[:limit]:
        title_el = entry.find(f"{_ATOM_NS}title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        link_el = entry.find(f"{_ATOM_NS}link")
        link = link_el.get("href", "").strip() if link_el is not None else ""

        summary_el = entry.find(f"{_ATOM_NS}summary")
        summary = (summary_el.text or "").strip() if summary_el is not None else ""

        pub_el = entry.find(f"{_ATOM_NS}published")
        if pub_el is None:
            pub_el = entry.find(f"{_ATOM_NS}updated")
        pub = (pub_el.text or "").strip() if pub_el is not None else ""

        items.append({
            "title": title,
            "url": link,
            "summary": summary[:300],
            "published": pub,
            "source": source,
        })
    return items


def parse_feed_xml(xml_text: str, limit: int = 10, source: str = "") -> list[dict]:
    """Parse RSS 2.0 or Atom XML into a list of item dicts."""
    root = ET.fromstring(xml_text)

    # Detect Atom vs RSS
    if root.tag == f"{_ATOM_NS}feed" or root.tag == "feed":
        return _parse_atom_entries(root, limit, source)

    # RSS 2.0 — root is <rss>
    return _parse_rss_items(root, limit, source)


async def fetch_feed(
    url: str,
    limit: int = 10,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Fetch and parse a single RSS/Atom feed."""
    _client = client or httpx.AsyncClient(timeout=10.0)
    own_client = client is None
    try:
        resp = await _client.get(url)
        resp.raise_for_status()
        return parse_feed_xml(resp.text, limit=limit, source=url)
    except Exception:
        return []
    finally:
        if own_client:
            await _client.aclose()


async def fetch_multiple_feeds(
    urls: list[str],
    limit_per_feed: int = 5,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Fetch multiple feeds concurrently and merge results."""
    _client = client or httpx.AsyncClient(timeout=10.0)
    own_client = client is None
    try:
        tasks = [fetch_feed(u, limit=limit_per_feed, client=_client) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[dict] = []
        for r in results:
            if isinstance(r, list):
                merged.extend(r)
        return merged
    finally:
        if own_client:
            await _client.aclose()
