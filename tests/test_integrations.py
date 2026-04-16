"""Tests for HTTP integrations — all HTTP calls are mocked."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.weather import (
    DEFAULT_LAT,
    DEFAULT_LON,
    fetch_weather_data,
    geocode_location,
    weather_code_to_condition,
)
from src.integrations.rss import fetch_feed, fetch_multiple_feeds, parse_feed_xml
from src.integrations.hackernews import fetch_top_stories
from src.integrations.github import (
    check_ci_status,
    fetch_repo_activity,
    fetch_user_repos,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_response(status_code: int = 200, json_data=None, text: str = ""):
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = text or (json.dumps(json_data) if json_data else "")
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp,
        )
    return resp


def _mock_client(response):
    """Build a mock httpx.AsyncClient whose .get() returns the given response."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    client.aclose = AsyncMock()
    return client


# ═══════════════════════════════════════════════════════════════════════
# Weather tests
# ═══════════════════════════════════════════════════════════════════════


MOCK_WEATHER_JSON = {
    "current": {"temperature_2m": 82.0, "weather_code": 1},
    "daily": {"temperature_2m_max": [90.0], "temperature_2m_min": [70.0]},
    "timezone": "America/Chicago",
}


class TestWeatherCodeMapping:
    def test_clear(self):
        assert weather_code_to_condition(0) == "Clear"

    def test_partly_cloudy_range(self):
        for code in (1, 2, 3):
            assert weather_code_to_condition(code) == "Partly cloudy"

    def test_foggy(self):
        for code in (45, 48):
            assert weather_code_to_condition(code) == "Foggy"

    def test_rain_range(self):
        for code in (51, 53, 55, 56, 57, 61, 63, 65, 67):
            assert weather_code_to_condition(code) == "Rain"

    def test_snow_range(self):
        for code in (71, 73, 75, 77):
            assert weather_code_to_condition(code) == "Snow"

    def test_showers(self):
        for code in (80, 81, 82):
            assert weather_code_to_condition(code) == "Showers"

    def test_thunderstorm(self):
        for code in (95, 96, 99):
            assert weather_code_to_condition(code) == "Thunderstorm"

    def test_unknown_code(self):
        assert weather_code_to_condition(999) == "Unknown"


class TestFetchWeatherData:
    @pytest.mark.asyncio
    async def test_parses_response(self):
        client = _mock_client(_mock_response(json_data=MOCK_WEATHER_JSON))
        result = await fetch_weather_data(30.0, -97.0, client=client)

        assert result["temp"] == 82.0
        assert result["condition"] == "Partly cloudy"
        assert result["high"] == 90.0
        assert result["low"] == 70.0
        assert "America" in result["location"]
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_uses_default_coords(self):
        client = _mock_client(_mock_response(json_data=MOCK_WEATHER_JSON))
        await fetch_weather_data(client=client)
        call_args = client.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params["latitude"] == DEFAULT_LAT
        assert params["longitude"] == DEFAULT_LON

    @pytest.mark.asyncio
    async def test_http_error_returns_fallback(self):
        client = _mock_client(_mock_response(status_code=500, json_data={}))
        result = await fetch_weather_data(30.0, -97.0, client=client)
        assert result.get("error") is True
        assert result["condition"] == "Unknown"


class TestGeocodeLocation:
    @pytest.mark.asyncio
    async def test_returns_coords(self):
        data = {"results": [{"latitude": 40.7128, "longitude": -74.0060}]}
        client = _mock_client(_mock_response(json_data=data))
        result = await geocode_location("New York", client=client)
        assert result == (40.7128, -74.0060)

    @pytest.mark.asyncio
    async def test_no_results_returns_none(self):
        client = _mock_client(_mock_response(json_data={}))
        result = await geocode_location("xyznonexistent", client=client)
        assert result is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self):
        client = _mock_client(_mock_response(status_code=500, json_data={}))
        result = await geocode_location("anywhere", client=client)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# RSS tests
# ═══════════════════════════════════════════════════════════════════════

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article One</title>
      <link>https://example.com/one</link>
      <description>First article description</description>
      <pubDate>Wed, 15 Apr 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/two</link>
      <description>Second article description</description>
      <pubDate>Wed, 15 Apr 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

MOCK_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Entry One</title>
    <link href="https://example.com/atom-one"/>
    <summary>First atom entry</summary>
    <published>2026-04-15T10:00:00Z</published>
  </entry>
  <entry>
    <title>Atom Entry Two</title>
    <link href="https://example.com/atom-two"/>
    <summary>Second atom entry</summary>
    <updated>2026-04-15T11:00:00Z</updated>
  </entry>
</feed>"""


class TestRSSParsing:
    def test_parse_rss_items(self):
        items = parse_feed_xml(MOCK_RSS_XML, limit=10, source="test")
        assert len(items) == 2
        assert items[0]["title"] == "Article One"
        assert items[0]["url"] == "https://example.com/one"
        assert items[0]["summary"] == "First article description"
        assert items[0]["source"] == "test"

    def test_parse_rss_limit(self):
        items = parse_feed_xml(MOCK_RSS_XML, limit=1, source="test")
        assert len(items) == 1

    def test_parse_rss_published(self):
        items = parse_feed_xml(MOCK_RSS_XML, limit=10, source="test")
        assert "Apr" in items[0]["published"]


class TestAtomParsing:
    def test_parse_atom_entries(self):
        items = parse_feed_xml(MOCK_ATOM_XML, limit=10, source="atom")
        assert len(items) == 2
        assert items[0]["title"] == "Atom Entry One"
        assert items[0]["url"] == "https://example.com/atom-one"
        assert items[0]["summary"] == "First atom entry"
        assert items[0]["source"] == "atom"

    def test_atom_uses_updated_when_no_published(self):
        items = parse_feed_xml(MOCK_ATOM_XML, limit=10, source="atom")
        # Second entry has <updated> but no <published>
        assert "2026" in items[1]["published"]

    def test_atom_limit(self):
        items = parse_feed_xml(MOCK_ATOM_XML, limit=1, source="atom")
        assert len(items) == 1


class TestFetchFeed:
    @pytest.mark.asyncio
    async def test_fetches_and_parses(self):
        client = _mock_client(_mock_response(text=MOCK_RSS_XML))
        items = await fetch_feed("https://example.com/feed", limit=10, client=client)
        assert len(items) == 2
        assert items[0]["title"] == "Article One"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        client = _mock_client(_mock_response(status_code=500))
        items = await fetch_feed("https://example.com/feed", client=client)
        assert items == []


class TestFetchMultipleFeeds:
    @pytest.mark.asyncio
    async def test_merges_feeds(self):
        client = _mock_client(_mock_response(text=MOCK_RSS_XML))
        items = await fetch_multiple_feeds(
            ["https://a.com/feed", "https://b.com/feed"],
            limit_per_feed=5,
            client=client,
        )
        # Two feeds, each with 2 items
        assert len(items) == 4

    @pytest.mark.asyncio
    async def test_handles_partial_failure(self):
        """One feed succeeds, the other fails — we still get results."""
        call_count = 0

        async def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(text=MOCK_RSS_XML)
            return _mock_response(status_code=500)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=side_effect)
        client.aclose = AsyncMock()

        items = await fetch_multiple_feeds(
            ["https://good.com/feed", "https://bad.com/feed"],
            limit_per_feed=5,
            client=client,
        )
        assert len(items) >= 2  # At least the good feed's items


# ═══════════════════════════════════════════════════════════════════════
# Hacker News tests
# ═══════════════════════════════════════════════════════════════════════


MOCK_HN_STORY_IDS = [1001, 1002, 1003, 1004]

MOCK_HN_STORIES = {
    1001: {"id": 1001, "title": "Show HN: Cool Project", "url": "https://cool.dev",
           "score": 250, "descendants": 42, "by": "alice"},
    1002: {"id": 1002, "title": "Low Score Post", "url": "https://low.dev",
           "score": 10, "descendants": 2, "by": "bob"},
    1003: {"id": 1003, "title": "Another Hit", "url": "https://hit.dev",
           "score": 300, "descendants": 100, "by": "carol"},
    1004: {"id": 1004, "title": "Medium Post", "url": "https://medium.dev",
           "score": 150, "descendants": 30, "by": "dave"},
}


class TestHackerNews:
    @pytest.mark.asyncio
    async def test_fetch_top_stories(self):
        async def mock_get(url, **kwargs):
            if "topstories" in url:
                return _mock_response(json_data=MOCK_HN_STORY_IDS)
            # Extract story ID from URL
            for sid, data in MOCK_HN_STORIES.items():
                if str(sid) in url:
                    return _mock_response(json_data=data)
            return _mock_response(json_data={})

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=mock_get)
        client.aclose = AsyncMock()

        stories = await fetch_top_stories(limit=10, min_score=100, client=client)
        assert len(stories) == 3  # 1001 (250), 1003 (300), 1004 (150)
        assert all(s["score"] >= 100 for s in stories)

    @pytest.mark.asyncio
    async def test_min_score_filtering(self):
        async def mock_get(url, **kwargs):
            if "topstories" in url:
                return _mock_response(json_data=MOCK_HN_STORY_IDS)
            for sid, data in MOCK_HN_STORIES.items():
                if str(sid) in url:
                    return _mock_response(json_data=data)
            return _mock_response(json_data={})

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=mock_get)
        client.aclose = AsyncMock()

        stories = await fetch_top_stories(limit=10, min_score=200, client=client)
        assert len(stories) == 2  # Only 1001 (250) and 1003 (300)
        assert all(s["score"] >= 200 for s in stories)

    @pytest.mark.asyncio
    async def test_limit_applied(self):
        async def mock_get(url, **kwargs):
            if "topstories" in url:
                return _mock_response(json_data=MOCK_HN_STORY_IDS)
            for sid, data in MOCK_HN_STORIES.items():
                if str(sid) in url:
                    return _mock_response(json_data=data)
            return _mock_response(json_data={})

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=mock_get)
        client.aclose = AsyncMock()

        stories = await fetch_top_stories(limit=1, min_score=100, client=client)
        assert len(stories) == 1

    @pytest.mark.asyncio
    async def test_story_dict_keys(self):
        async def mock_get(url, **kwargs):
            if "topstories" in url:
                return _mock_response(json_data=[1001])
            return _mock_response(json_data=MOCK_HN_STORIES[1001])

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=mock_get)
        client.aclose = AsyncMock()

        stories = await fetch_top_stories(limit=5, min_score=0, client=client)
        assert len(stories) >= 1
        s = stories[0]
        assert "title" in s
        assert "url" in s
        assert "score" in s
        assert "comments" in s
        assert "author" in s
        assert "hn_url" in s


# ═══════════════════════════════════════════════════════════════════════
# GitHub tests
# ═══════════════════════════════════════════════════════════════════════


MOCK_GITHUB_ISSUES = [
    {"title": "Bug in parser", "html_url": "https://github.com/o/r/issues/1",
     "number": 1, "user": {"login": "alice"}},
    {"title": "Add feature X", "html_url": "https://github.com/o/r/pulls/2",
     "number": 2, "user": {"login": "bob"}, "pull_request": {"url": "..."}},
]


class TestGitHubRepoActivity:
    @pytest.mark.asyncio
    async def test_via_gh_cli(self):
        """When gh CLI succeeds, it parses issues and PRs."""
        gh_output = json.dumps(MOCK_GITHUB_ISSUES)

        with patch("src.integrations.github._run_gh") as mock_gh:
            # First call: issues; Second call: CI status
            mock_gh.side_effect = [
                (0, gh_output),  # issues
                (0, json.dumps([{"status": "completed", "conclusion": "success"}])),  # CI
            ]
            result = await fetch_repo_activity("owner/repo")

        assert len(result["open_issues"]) == 1
        assert result["open_issues"][0]["title"] == "Bug in parser"
        assert len(result["recent_prs"]) == 1
        assert result["recent_prs"][0]["title"] == "Add feature X"
        assert result["ci_status"] == "passing"

    @pytest.mark.asyncio
    async def test_fallback_to_httpx(self):
        """When gh CLI fails, falls back to httpx."""
        client = _mock_client(_mock_response(json_data=MOCK_GITHUB_ISSUES))

        with patch("src.integrations.github._run_gh") as mock_gh:
            mock_gh.side_effect = [
                (1, ""),  # gh fails for issues
                (1, ""),  # gh fails for CI
            ]
            result = await fetch_repo_activity("owner/repo", client=client)

        assert len(result["open_issues"]) == 1
        assert len(result["recent_prs"]) == 1
        assert result["ci_status"] is None

    @pytest.mark.asyncio
    async def test_both_fail_returns_empty(self):
        """When both gh and httpx fail, returns empty lists."""
        client = _mock_client(_mock_response(status_code=500, json_data={}))

        with patch("src.integrations.github._run_gh") as mock_gh:
            mock_gh.side_effect = [
                (1, ""),  # gh fails
                (1, ""),  # CI fails
            ]
            result = await fetch_repo_activity("owner/repo", client=client)

        assert result["open_issues"] == []
        assert result["recent_prs"] == []
        assert result["ci_status"] is None


class TestGitHubUserRepos:
    @pytest.mark.asyncio
    async def test_returns_repo_list(self):
        repos_json = json.dumps([
            {"nameWithOwner": "alice/project-a"},
            {"nameWithOwner": "alice/project-b"},
        ])
        with patch("src.integrations.github._run_gh", return_value=(0, repos_json)):
            repos = await fetch_user_repos(limit=10)
        assert repos == ["alice/project-a", "alice/project-b"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self):
        with patch("src.integrations.github._run_gh", return_value=(1, "")):
            repos = await fetch_user_repos()
        assert repos == []


class TestCIStatus:
    @pytest.mark.asyncio
    async def test_passing(self):
        data = json.dumps([{"status": "completed", "conclusion": "success"}])
        with patch("src.integrations.github._run_gh", return_value=(0, data)):
            status = await check_ci_status("owner/repo")
        assert status == "passing"

    @pytest.mark.asyncio
    async def test_failing(self):
        data = json.dumps([{"status": "completed", "conclusion": "failure"}])
        with patch("src.integrations.github._run_gh", return_value=(0, data)):
            status = await check_ci_status("owner/repo")
        assert status == "failing"

    @pytest.mark.asyncio
    async def test_pending(self):
        data = json.dumps([{"status": "in_progress", "conclusion": ""}])
        with patch("src.integrations.github._run_gh", return_value=(0, data)):
            status = await check_ci_status("owner/repo")
        assert status == "pending"

    @pytest.mark.asyncio
    async def test_none_on_failure(self):
        with patch("src.integrations.github._run_gh", return_value=(1, "")):
            status = await check_ci_status("owner/repo")
        assert status is None

    @pytest.mark.asyncio
    async def test_none_on_empty_runs(self):
        with patch("src.integrations.github._run_gh", return_value=(0, "[]")):
            status = await check_ci_status("owner/repo")
        assert status is None


# ═══════════════════════════════════════════════════════════════════════
# Briefing sections with real integrations (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════


class TestBriefingSectionsIntegration:
    @pytest.mark.asyncio
    async def test_weather_section_uses_real_integration(self):
        from src.briefing.sections import fetch_weather

        with patch("src.integrations.weather.fetch_weather_data") as mock_fetch:
            mock_fetch.return_value = {
                "temp": 75,
                "condition": "Clear",
                "high": 88,
                "low": 65,
                "summary": "Clear in Austin. High of 88 °F, low of 65 °F.",
                "location": "America, Chicago",
            }
            with patch("src.integrations.weather.geocode_location", return_value=None):
                section = await fetch_weather()

        assert not section.empty
        assert section.title == "Weather"
        assert section.items[0]["temp"] == 75

    @pytest.mark.asyncio
    async def test_weather_section_fallback_on_error(self):
        from src.briefing.sections import fetch_weather

        with patch("src.integrations.weather.fetch_weather_data", side_effect=Exception("boom")):
            with patch("src.integrations.weather.geocode_location", return_value=None):
                section = await fetch_weather()

        assert not section.empty
        assert "Partly cloudy" in section.content  # mock fallback

    @pytest.mark.asyncio
    async def test_news_section_with_hn(self):
        from src.briefing.sections import fetch_news

        with patch("src.integrations.hackernews.fetch_top_stories") as mock_hn:
            mock_hn.return_value = [
                {"title": "Cool Story", "hn_url": "https://hn.com/1", "score": 200},
            ]
            section = await fetch_news(hn_enabled=True)

        assert not section.empty
        assert "1 headline" in section.content

    @pytest.mark.asyncio
    async def test_news_section_empty_when_no_results(self):
        from src.briefing.sections import fetch_news

        with patch("src.integrations.hackernews.fetch_top_stories", return_value=[]):
            section = await fetch_news(hn_enabled=True)

        assert section.empty

    @pytest.mark.asyncio
    async def test_github_section_with_activity(self):
        from src.briefing.sections import fetch_github

        with patch("src.integrations.github.fetch_repo_activity") as mock_act:
            mock_act.return_value = {
                "open_issues": [{"title": "Bug", "url": "http://...", "number": 1, "user": "a"}],
                "recent_prs": [],
                "ci_status": "passing",
            }
            section = await fetch_github(["owner/repo"])

        assert not section.empty
        assert "1 open issue" in section.content

    @pytest.mark.asyncio
    async def test_github_section_fallback_on_error(self):
        from src.briefing.sections import fetch_github

        with patch("src.integrations.github.fetch_repo_activity", side_effect=Exception("oops")):
            section = await fetch_github(["owner/repo"])

        assert section.empty  # graceful degradation


# ═══════════════════════════════════════════════════════════════════════
# Scout scanners with real integrations (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════


class TestScoutScannersIntegration:
    @pytest.mark.asyncio
    async def test_rss_scanner_uses_integration(self):
        from src.scout.scanner import scan_rss

        with patch("src.integrations.rss.fetch_multiple_feeds") as mock_feeds:
            mock_feeds.return_value = [
                {"title": "Real Article", "url": "https://real.com", "summary": "Good stuff",
                 "published": "2026-04-15", "source": "https://real.com/feed"},
            ]
            candidates = await scan_rss(["https://real.com/feed"])

        assert len(candidates) >= 1
        assert candidates[0].name == "Real Article"

    @pytest.mark.asyncio
    async def test_rss_scanner_falls_back_to_mock(self):
        from src.scout.scanner import scan_rss

        with patch("src.integrations.rss.fetch_multiple_feeds", return_value=[]):
            candidates = await scan_rss(["https://example.com/feed"])

        assert len(candidates) >= 1  # Mock fallback

    @pytest.mark.asyncio
    async def test_hackernews_scanner_uses_integration(self):
        from src.scout.scanner import scan_hackernews

        with patch("src.integrations.hackernews.fetch_top_stories") as mock_hn:
            mock_hn.return_value = [
                {"title": "Real HN Post", "score": 500, "hn_url": "https://hn.com/123",
                 "comments": 42},
            ]
            candidates = await scan_hackernews(min_score=100)

        assert len(candidates) >= 1
        assert candidates[0].name == "Real HN Post"
        assert candidates[0].metadata["score"] == 500

    @pytest.mark.asyncio
    async def test_hackernews_scanner_falls_back(self):
        from src.scout.scanner import scan_hackernews

        with patch("src.integrations.hackernews.fetch_top_stories", return_value=[]):
            candidates = await scan_hackernews(min_score=100)

        assert len(candidates) >= 1  # Mock fallback

    @pytest.mark.asyncio
    async def test_github_scanner_uses_integration(self):
        from src.scout.scanner import scan_github_repos

        with patch("src.integrations.github.fetch_user_repos", return_value=["a/b"]):
            with patch("src.integrations.github.fetch_repo_activity") as mock_act:
                mock_act.return_value = {
                    "open_issues": [
                        {"title": "Fix crash", "url": "https://github.com/a/b/issues/5",
                         "number": 5, "user": "alice"},
                    ],
                    "recent_prs": [],
                    "ci_status": None,
                }
                candidates = await scan_github_repos()

        assert len(candidates) >= 1
        assert "Fix crash" in candidates[0].name

    @pytest.mark.asyncio
    async def test_github_scanner_falls_back_on_error(self):
        from src.scout.scanner import scan_github_repos

        with patch("src.integrations.github.fetch_user_repos", side_effect=Exception("fail")):
            candidates = await scan_github_repos()

        assert len(candidates) >= 1  # Mock fallback


# ═══════════════════════════════════════════════════════════════════════
# Error handling tests
# ═══════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_weather_timeout_returns_fallback(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client.aclose = AsyncMock()

        result = await fetch_weather_data(30.0, -97.0, client=client)
        assert result.get("error") is True
        assert result["summary"] == "Weather data unavailable."

    @pytest.mark.asyncio
    async def test_rss_malformed_xml(self):
        client = _mock_client(_mock_response(text="<not valid xml!>!>"))
        items = await fetch_feed("https://bad.com/feed", client=client)
        assert items == []  # Returns empty on parse error

    @pytest.mark.asyncio
    async def test_hackernews_malformed_json(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.side_effect = json.JSONDecodeError("bad", "", 0)
        client.get = AsyncMock(return_value=resp)
        client.aclose = AsyncMock()

        # Should raise since the top-level call has no try/except
        with pytest.raises(json.JSONDecodeError):
            await fetch_top_stories(limit=5, min_score=0, client=client)

    @pytest.mark.asyncio
    async def test_github_malformed_json_from_gh_cli(self):
        with patch("src.integrations.github._run_gh") as mock_gh:
            mock_gh.side_effect = [
                (0, "NOT JSON"),  # issues: malformed
                (1, ""),          # CI: fail
            ]
            # Should fallback to httpx; both mocked to also fail -> empty
            client = _mock_client(_mock_response(status_code=500, json_data={}))
            result = await fetch_repo_activity("owner/repo", client=client)

        assert result["open_issues"] == []
        assert result["recent_prs"] == []

    @pytest.mark.asyncio
    async def test_geocode_timeout(self):
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        client.aclose = AsyncMock()

        result = await geocode_location("Austin", client=client)
        assert result is None  # Graceful None, no crash
