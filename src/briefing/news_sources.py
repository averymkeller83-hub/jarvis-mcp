"""Curated news source catalog for briefing headlines."""

from __future__ import annotations

from dataclasses import dataclass

# ── Source catalog ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class NewsSource:
    """A single news outlet with its RSS feed URL."""

    id: str
    name: str
    rss_url: str
    category: str  # "general", "tech", "business", "world", "science", "sports"


# Every source we ship out of the box.  Users toggle these on/off.
NEWS_CATALOG: list[NewsSource] = [
    # ── General / Headlines ────────────────────────────────────────
    NewsSource("google_news", "Google News", "https://news.google.com/rss", "general"),
    NewsSource("ap_news", "AP News", "https://apnews.com/index.rss", "general"),
    NewsSource("bbc", "BBC News", "https://feeds.bbci.co.uk/news/rss.xml", "general"),
    NewsSource("nyt", "New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "general"),
    NewsSource("reuters", "Reuters", "https://www.rss.reuters.com/news/topNews", "general"),
    NewsSource("cnn", "CNN", "http://rss.cnn.com/rss/cnn_topstories.rss", "general"),
    NewsSource("npr", "NPR", "https://feeds.npr.org/1001/rss.xml", "general"),

    # ── Tech ───────────────────────────────────────────────────────
    NewsSource("hackernews", "Hacker News", "", "tech"),  # special: uses HN API, not RSS
    NewsSource("techcrunch", "TechCrunch", "https://techcrunch.com/feed/", "tech"),
    NewsSource("verge", "The Verge", "https://www.theverge.com/rss/index.xml", "tech"),
    NewsSource("ars", "Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "tech"),
    NewsSource("wired", "Wired", "https://www.wired.com/feed/rss", "tech"),
    NewsSource("apple_newsroom", "Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss", "tech"),

    # ── Business ───────────────────────────────────────────────────
    NewsSource("cnbc", "CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "business"),
    NewsSource("bloomberg", "Bloomberg", "https://feeds.bloomberg.com/markets/news.rss", "business"),

    # ── Science ────────────────────────────────────────────────────
    NewsSource("nasa", "NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss", "science"),

    # ── Sports ─────────────────────────────────────────────────────
    NewsSource("espn", "ESPN", "https://www.espn.com/espn/rss/news", "sports"),
]

# Quick lookup by ID
_CATALOG_MAP: dict[str, NewsSource] = {s.id: s for s in NEWS_CATALOG}

CATEGORIES = sorted({s.category for s in NEWS_CATALOG})


def get_source(source_id: str) -> NewsSource | None:
    """Look up a news source by its ID."""
    return _CATALOG_MAP.get(source_id)


def get_catalog() -> list[dict]:
    """Return the full catalog as serializable dicts."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "rss_url": s.rss_url,
        }
        for s in NEWS_CATALOG
    ]


def get_rss_urls_for_enabled(enabled_ids: list[str]) -> tuple[list[str], bool]:
    """Given a list of enabled source IDs, return (rss_urls, hn_enabled).

    Hacker News is special-cased since it uses its own API, not RSS.
    """
    rss_urls: list[str] = []
    hn_enabled = False

    for sid in enabled_ids:
        src = _CATALOG_MAP.get(sid)
        if src is None:
            continue
        if src.id == "hackernews":
            hn_enabled = True
        elif src.rss_url:
            rss_urls.append(src.rss_url)

    return rss_urls, hn_enabled
