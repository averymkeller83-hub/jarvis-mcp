"""Comprehensive tests for the Scout module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from src.scout.cards import ScoutCard, build_card, card_to_dict, card_to_markdown
from src.scout.engine import install_candidate, run_discovery
from src.scout.sandbox import SandboxResult, cleanup_expired, is_sandbox_expired, sandbox_test
from src.scout.scanner import (
    Candidate,
    ScanResult,
    scan_anthropic_changelog,
    scan_github_repos,
    scan_github_trending,
    scan_hackernews,
    scan_mcp_registry,
    scan_rss,
    scan_source,
)
from src.scout.scorer import ScoredCandidate, rank_candidates, score_candidate
from src.scout.signals import Signal, get_source_weights, load_signals, log_signal
from src.scout.sources import (
    ScoutSource,
    get_daily_sources,
    get_enabled_sources,
    get_hourly_sources,
    load_sources,
)
from src.server.app import app


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


@pytest.fixture
def example_config_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "config" / "scout_sources.example.toml")


@pytest.fixture
def enabled_config(tmp_path: Path) -> str:
    """Create a temp TOML with some sources enabled."""
    content = """
[sources.anthropic_changelog]
enabled = true
cadence = "hourly"
description = "Anthropic changelog"

[sources.mcp_registry]
enabled = true
cadence = "daily"
urls = ["https://mcp.so"]
description = "MCP registry"

[sources.hackernews]
enabled = false
cadence = "daily"
min_score = 200
description = "Hacker News"

[sources.github_repos]
enabled = true
cadence = "hourly"
description = "GitHub repos"
"""
    p = tmp_path / "scout_sources.toml"
    p.write_text(content)
    return str(p)


@pytest.fixture
def sample_candidate() -> Candidate:
    return Candidate(
        id="test-001",
        name="mcp-sqlite-explorer",
        pitch="Browse SQLite databases from Claude",
        source="mcp_registry",
        source_url="https://mcp.so/server/sqlite",
        candidate_type="mcp_server",
        metadata={"stars": 100},
    )


@pytest.fixture
def sample_rss_candidate() -> Candidate:
    return Candidate(
        id="test-002",
        name="AI Weekly Roundup",
        pitch="Summary of the week in AI",
        source="rss_curated",
        source_url="https://example.com/ai-weekly",
        candidate_type="rss_item",
        metadata={"author": "Test Author"},
    )


@pytest.fixture
def sample_changelog_candidate() -> Candidate:
    return Candidate(
        id="test-003",
        name="Claude 4.5 Release",
        pitch="New Claude model with extended thinking",
        source="anthropic_changelog",
        source_url="https://docs.anthropic.com/changelog",
        candidate_type="changelog",
        metadata={"version": "4.5"},
    )


# ── Source loading tests ────────────────────────────────────────────────


class TestSourceLoading:
    def test_load_sources_from_example(self, example_config_path: str):
        sources = load_sources(example_config_path)
        assert len(sources) > 0
        names = [s.name for s in sources]
        assert "anthropic_changelog" in names
        assert "mcp_registry" in names
        assert "hackernews" in names

    def test_load_sources_returns_scout_source_dataclass(self, example_config_path: str):
        sources = load_sources(example_config_path)
        for s in sources:
            assert isinstance(s, ScoutSource)
            assert isinstance(s.name, str)
            assert isinstance(s.enabled, bool)
            assert s.cadence in ("hourly", "daily", "on_demand")

    def test_load_sources_missing_file_returns_empty(self):
        sources = load_sources("/nonexistent/path.toml")
        assert sources == []

    def test_load_sources_urls_populated_for_mcp_registry(self, example_config_path: str):
        sources = load_sources(example_config_path)
        mcp = [s for s in sources if s.name == "mcp_registry"][0]
        assert len(mcp.urls) > 0
        assert "https://glama.ai" in mcp.urls or "https://mcp.so" in mcp.urls

    def test_load_sources_rss_feeds_as_urls(self, example_config_path: str):
        sources = load_sources(example_config_path)
        rss = [s for s in sources if s.name == "rss_curated"][0]
        assert len(rss.urls) > 0

    def test_load_sources_extra_config_preserved(self, example_config_path: str):
        sources = load_sources(example_config_path)
        hn = [s for s in sources if s.name == "hackernews"][0]
        assert "min_score" in hn.config
        assert hn.config["min_score"] == 100


class TestSourceFiltering:
    def test_get_enabled_sources_empty_when_all_disabled(self, example_config_path: str):
        enabled = get_enabled_sources(example_config_path)
        assert len(enabled) == 0  # example file has all disabled

    def test_get_enabled_sources_returns_only_enabled(self, enabled_config: str):
        enabled = get_enabled_sources(enabled_config)
        assert len(enabled) == 3
        for s in enabled:
            assert s.enabled is True

    def test_get_hourly_sources(self, enabled_config: str):
        hourly = get_hourly_sources(enabled_config)
        assert len(hourly) == 2  # anthropic_changelog + github_repos
        for s in hourly:
            assert s.cadence == "hourly"
            assert s.enabled is True

    def test_get_daily_sources(self, enabled_config: str):
        daily = get_daily_sources(enabled_config)
        assert len(daily) == 1  # mcp_registry
        for s in daily:
            assert s.cadence == "daily"
            assert s.enabled is True


# ── Scanner tests ───────────────────────────────────────────────────────


class TestScanners:
    @pytest.mark.asyncio
    async def test_scan_anthropic_changelog_returns_candidates(self):
        candidates = await scan_anthropic_changelog()
        assert len(candidates) > 0
        c = candidates[0]
        assert isinstance(c, Candidate)
        assert c.source == "anthropic_changelog"
        assert c.candidate_type == "changelog"

    @pytest.mark.asyncio
    async def test_scan_mcp_registry_returns_candidates(self):
        candidates = await scan_mcp_registry(["https://mcp.so"])
        assert len(candidates) > 0
        c = candidates[0]
        assert c.candidate_type == "mcp_server"
        assert c.source == "mcp_registry"

    @pytest.mark.asyncio
    async def test_scan_github_repos_returns_candidates(self):
        candidates = await scan_github_repos()
        assert len(candidates) > 0
        c = candidates[0]
        assert c.candidate_type == "github_issue"

    @pytest.mark.asyncio
    async def test_scan_github_trending_returns_candidates(self):
        candidates = await scan_github_trending(["python"])
        assert len(candidates) > 0
        c = candidates[0]
        assert c.candidate_type == "cli"
        assert "python" in c.pitch.lower() or "python" in c.metadata.get("language", "")

    @pytest.mark.asyncio
    async def test_scan_rss_returns_candidates(self):
        candidates = await scan_rss(["https://example.com/feed.xml"])
        assert len(candidates) > 0
        c = candidates[0]
        assert c.candidate_type == "rss_item"

    @pytest.mark.asyncio
    async def test_scan_hackernews_returns_candidates(self):
        candidates = await scan_hackernews(min_score=50)
        assert len(candidates) > 0
        c = candidates[0]
        assert c.candidate_type == "rss_item"
        assert c.metadata["score"] >= 50

    @pytest.mark.asyncio
    async def test_candidate_has_required_fields(self):
        candidates = await scan_anthropic_changelog()
        c = candidates[0]
        assert c.id
        assert c.name
        assert c.pitch
        assert c.source
        assert c.candidate_type
        assert c.discovered_at


class TestScanSourceDispatcher:
    @pytest.mark.asyncio
    async def test_dispatcher_routes_anthropic_changelog(self):
        source = ScoutSource(
            name="anthropic_changelog", enabled=True, cadence="hourly",
            description="test",
        )
        result = await scan_source(source)
        assert isinstance(result, ScanResult)
        assert result.source == "anthropic_changelog"
        assert len(result.candidates) > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_dispatcher_routes_mcp_registry(self):
        source = ScoutSource(
            name="mcp_registry", enabled=True, cadence="daily",
            description="test", urls=["https://mcp.so"],
        )
        result = await scan_source(source)
        assert result.source == "mcp_registry"
        assert len(result.candidates) > 0

    @pytest.mark.asyncio
    async def test_dispatcher_routes_github_repos(self):
        source = ScoutSource(
            name="github_repos", enabled=True, cadence="hourly",
            description="test",
        )
        result = await scan_source(source)
        assert result.source == "github_repos"
        assert len(result.candidates) > 0

    @pytest.mark.asyncio
    async def test_dispatcher_routes_github_trending(self):
        source = ScoutSource(
            name="github_trending", enabled=True, cadence="daily",
            description="test", config={"languages": ["rust"]},
        )
        result = await scan_source(source)
        assert result.source == "github_trending"
        assert len(result.candidates) > 0

    @pytest.mark.asyncio
    async def test_dispatcher_routes_rss_curated(self):
        source = ScoutSource(
            name="rss_curated", enabled=True, cadence="daily",
            description="test", urls=["https://example.com/feed"],
        )
        result = await scan_source(source)
        assert result.source == "rss_curated"
        assert len(result.candidates) > 0

    @pytest.mark.asyncio
    async def test_dispatcher_routes_hackernews(self):
        source = ScoutSource(
            name="hackernews", enabled=True, cadence="daily",
            description="test", config={"min_score": 200},
        )
        result = await scan_source(source)
        assert result.source == "hackernews"
        assert len(result.candidates) > 0

    @pytest.mark.asyncio
    async def test_dispatcher_unknown_source_returns_error(self):
        source = ScoutSource(
            name="unknown_xyz", enabled=True, cadence="daily",
            description="test",
        )
        result = await scan_source(source)
        assert result.error is not None
        assert "Unknown source" in result.error
        assert len(result.candidates) == 0


# ── Scorer tests ────────────────────────────────────────────────────────


class TestScorer:
    def test_score_returns_valid_range(self, sample_candidate: Candidate):
        scored = score_candidate(sample_candidate)
        assert 0.0 <= scored.relevance_score <= 1.0

    def test_executable_type_requires_sandbox(self, sample_candidate: Candidate):
        scored = score_candidate(sample_candidate)
        assert scored.sandbox_required is True

    def test_rss_type_no_sandbox(self, sample_rss_candidate: Candidate):
        scored = score_candidate(sample_rss_candidate)
        assert scored.sandbox_required is False

    def test_changelog_type_no_sandbox(self, sample_changelog_candidate: Candidate):
        scored = score_candidate(sample_changelog_candidate)
        assert scored.sandbox_required is False

    def test_executable_base_score_higher_than_info(
        self, sample_candidate: Candidate, sample_rss_candidate: Candidate,
    ):
        exec_scored = score_candidate(sample_candidate)
        info_scored = score_candidate(sample_rss_candidate)
        # Base executable score is 0.5, info is 0.3 (before bonuses)
        assert exec_scored.relevance_score >= 0.5
        assert info_scored.relevance_score >= 0.3

    def test_user_context_stack_boosts_score(self, sample_candidate: Candidate):
        base = score_candidate(sample_candidate)
        boosted = score_candidate(sample_candidate, user_context={"stack": ["sqlite"]})
        assert boosted.relevance_score >= base.relevance_score

    def test_user_context_project_boosts_score(self):
        c = Candidate(
            id="proj-test", name="jarvis-mcp helper",
            pitch="A tool for the jarvis project",
            source="github_trending", source_url=None,
            candidate_type="cli",
        )
        boosted = score_candidate(c, user_context={"projects": ["jarvis"]})
        assert any("project" in r for r in boosted.match_reasons)

    def test_user_context_topic_boosts_score(self):
        c = Candidate(
            id="topic-test", name="MCP deep dive",
            pitch="Everything about model context protocol",
            source="rss_curated", source_url=None,
            candidate_type="rss_item",
        )
        boosted = score_candidate(c, user_context={"recent_topics": ["protocol"]})
        assert any("topic" in r for r in boosted.match_reasons)

    def test_match_reasons_populated(self, sample_candidate: Candidate):
        scored = score_candidate(sample_candidate)
        assert len(scored.match_reasons) > 0

    def test_score_clamped_to_one(self):
        """Even with all bonuses, score should not exceed 1.0."""
        c = Candidate(
            id="max-test", name="python fastapi mcp claude ai agent",
            pitch="python sqlite react typescript node rust go",
            source="anthropic_changelog", source_url=None,
            candidate_type="mcp_server",
        )
        ctx = {
            "stack": ["python", "fastapi", "mcp"],
            "projects": ["claude"],
            "recent_topics": ["agent"],
        }
        scored = score_candidate(c, ctx)
        assert scored.relevance_score <= 1.0


class TestRanking:
    def test_rank_returns_top_n(self):
        candidates = [
            ScoredCandidate(
                candidate=Candidate(
                    id=f"r-{i}", name=f"c{i}", pitch="test", source="test",
                    source_url=None, candidate_type="rss_item",
                ),
                relevance_score=i * 0.1,
                match_reasons=["test"],
            )
            for i in range(10)
        ]
        top = rank_candidates(candidates, limit=3)
        assert len(top) == 3
        assert top[0].relevance_score >= top[1].relevance_score
        assert top[1].relevance_score >= top[2].relevance_score

    def test_rank_sorted_descending(self):
        candidates = [
            ScoredCandidate(
                candidate=Candidate(
                    id="low", name="low", pitch="t", source="t",
                    source_url=None, candidate_type="rss_item",
                ),
                relevance_score=0.1,
            ),
            ScoredCandidate(
                candidate=Candidate(
                    id="high", name="high", pitch="t", source="t",
                    source_url=None, candidate_type="rss_item",
                ),
                relevance_score=0.9,
            ),
        ]
        top = rank_candidates(candidates, limit=5)
        assert top[0].candidate.id == "high"
        assert top[1].candidate.id == "low"


# ── Sandbox tests ───────────────────────────────────────────────────────


class TestSandbox:
    @pytest.mark.asyncio
    async def test_sandbox_non_executable_passes_immediately(self, sample_rss_candidate):
        result = await sandbox_test(sample_rss_candidate)
        assert isinstance(result, SandboxResult)
        assert result.passed is True
        assert "No sandbox required" in result.test_log[0]

    @pytest.mark.asyncio
    async def test_sandbox_executable_runs_simulated_flow(self, sample_candidate):
        result = await sandbox_test(sample_candidate)
        assert result.passed is True
        assert len(result.test_log) > 1
        assert "All tests passed." in result.test_log

    @pytest.mark.asyncio
    async def test_sandbox_result_has_timestamps(self, sample_candidate):
        result = await sandbox_test(sample_candidate)
        assert result.tested_at
        assert result.expires_at
        # expires_at should be 7 days after tested_at
        tested = datetime.fromisoformat(result.tested_at)
        expires = datetime.fromisoformat(result.expires_at)
        diff = expires - tested
        assert diff.days == 7

    @pytest.mark.asyncio
    async def test_sandbox_changelog_passes_immediately(self, sample_changelog_candidate):
        result = await sandbox_test(sample_changelog_candidate)
        assert result.passed is True

    def test_is_sandbox_expired_false_for_fresh(self):
        result = SandboxResult(
            candidate_id="fresh",
            passed=True,
            test_log=["ok"],
        )
        assert is_sandbox_expired(result) is False

    def test_is_sandbox_expired_true_for_old(self):
        old_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        result = SandboxResult(
            candidate_id="old",
            passed=True,
            test_log=["ok"],
            tested_at=old_time,
            expires_at=(
                datetime.fromisoformat(old_time) + timedelta(days=7)
            ).isoformat(),
        )
        assert is_sandbox_expired(result) is True

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_results(self):
        old_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        results = [
            SandboxResult(
                candidate_id="old",
                passed=True,
                test_log=["ok"],
                tested_at=old_time,
                expires_at=(
                    datetime.fromisoformat(old_time) + timedelta(days=7)
                ).isoformat(),
            ),
            SandboxResult(
                candidate_id="fresh",
                passed=True,
                test_log=["ok"],
            ),
        ]
        count = await cleanup_expired(results)
        assert count == 1
        assert len(results) == 1
        assert results[0].candidate_id == "fresh"


# ── Card tests ──────────────────────────────────────────────────────────


class TestCards:
    def _make_scored(self, candidate: Candidate, sandbox_req: bool) -> ScoredCandidate:
        return ScoredCandidate(
            candidate=candidate,
            relevance_score=0.75,
            match_reasons=["matches your Python stack", "high-quality source"],
            sandbox_required=sandbox_req,
        )

    def test_build_card_from_scored_and_sandbox(self, sample_candidate: Candidate):
        scored = self._make_scored(sample_candidate, sandbox_req=True)
        sb = SandboxResult(
            candidate_id=sample_candidate.id, passed=True, test_log=["ok"],
        )
        card = build_card(scored, sb)
        assert isinstance(card, ScoutCard)
        assert card.candidate_id == sample_candidate.id
        assert card.name == sample_candidate.name
        assert card.sandbox_status == "passed"
        assert card.install_available is True

    def test_build_card_pending_sandbox(self, sample_candidate: Candidate):
        scored = self._make_scored(sample_candidate, sandbox_req=True)
        card = build_card(scored, None)
        assert card.sandbox_status == "pending"
        assert card.install_available is False

    def test_build_card_not_required_sandbox(self, sample_rss_candidate: Candidate):
        scored = self._make_scored(sample_rss_candidate, sandbox_req=False)
        card = build_card(scored, None)
        assert card.sandbox_status == "not_required"
        assert card.install_available is True

    def test_card_to_markdown_renders(self, sample_candidate: Candidate):
        scored = self._make_scored(sample_candidate, sandbox_req=True)
        sb = SandboxResult(
            candidate_id=sample_candidate.id, passed=True, test_log=["ok"],
        )
        card = build_card(scored, sb)
        md = card_to_markdown(card)
        assert sample_candidate.name in md
        assert "mcp_registry" in md
        assert "passed" in md

    def test_card_to_dict_is_json_serializable(self, sample_candidate: Candidate):
        scored = self._make_scored(sample_candidate, sandbox_req=True)
        sb = SandboxResult(
            candidate_id=sample_candidate.id, passed=True, test_log=["ok"],
        )
        card = build_card(scored, sb)
        d = card_to_dict(card)
        # Should not raise
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        assert parsed["candidate_id"] == sample_candidate.id
        assert parsed["name"] == sample_candidate.name

    def test_card_to_dict_has_all_fields(self, sample_candidate: Candidate):
        scored = self._make_scored(sample_candidate, sandbox_req=True)
        card = build_card(scored, None)
        d = card_to_dict(card)
        required_keys = {
            "candidate_id", "name", "pitch", "source_badge",
            "match_reason", "sandbox_status", "install_available", "details",
        }
        assert required_keys.issubset(d.keys())


# ── Signal tests ────────────────────────────────────────────────────────


class TestSignals:
    def test_log_and_load_signals(self, tmp_path: Path):
        log_path = str(tmp_path / "signals.jsonl")
        sig = Signal(
            candidate_id="sig-001", action="installed", reason="Looks useful",
        )
        log_signal(sig, log_path)
        loaded = load_signals(log_path)
        assert len(loaded) == 1
        assert loaded[0].candidate_id == "sig-001"
        assert loaded[0].action == "installed"
        assert loaded[0].reason == "Looks useful"

    def test_log_multiple_signals(self, tmp_path: Path):
        log_path = str(tmp_path / "signals.jsonl")
        for action in ("installed", "dismissed", "expanded", "ignored"):
            sig = Signal(candidate_id=f"sig-{action}", action=action)
            log_signal(sig, log_path)
        loaded = load_signals(log_path)
        assert len(loaded) == 4

    def test_load_signals_empty_file(self, tmp_path: Path):
        log_path = str(tmp_path / "empty.jsonl")
        loaded = load_signals(log_path)
        assert loaded == []

    def test_signal_has_timestamp(self, tmp_path: Path):
        log_path = str(tmp_path / "signals.jsonl")
        sig = Signal(candidate_id="ts-test", action="expanded")
        log_signal(sig, log_path)
        loaded = load_signals(log_path)
        assert loaded[0].timestamp
        # Should parse as ISO datetime
        datetime.fromisoformat(loaded[0].timestamp)

    def test_get_source_weights_installs_boost(self):
        signals = [
            Signal(candidate_id="source-a", action="installed"),
            Signal(candidate_id="source-a", action="installed"),
        ]
        weights = get_source_weights(signals)
        assert weights["source-a"] == 2.0

    def test_get_source_weights_dismissals_penalize(self):
        signals = [
            Signal(candidate_id="source-b", action="dismissed"),
        ]
        weights = get_source_weights(signals)
        assert weights["source-b"] == -0.5

    def test_get_source_weights_mixed(self):
        signals = [
            Signal(candidate_id="source-c", action="installed"),
            Signal(candidate_id="source-c", action="dismissed"),
        ]
        weights = get_source_weights(signals)
        assert weights["source-c"] == 0.5  # 1.0 + (-0.5)


# ── Engine integration tests ────────────────────────────────────────────


class TestEngine:
    @pytest.mark.asyncio
    async def test_run_discovery_with_sources(self, enabled_config: str):
        from src.scout.sources import load_sources as _load

        sources = [s for s in _load(enabled_config) if s.enabled]
        cards = await run_discovery(sources=sources)
        assert isinstance(cards, list)
        assert len(cards) > 0
        for card in cards:
            assert isinstance(card, ScoutCard)

    @pytest.mark.asyncio
    async def test_run_discovery_empty_sources(self):
        cards = await run_discovery(sources=[])
        assert cards == []

    @pytest.mark.asyncio
    async def test_run_discovery_with_user_context(self, enabled_config: str):
        from src.scout.sources import load_sources as _load

        sources = [s for s in _load(enabled_config) if s.enabled]
        ctx = {"stack": ["python", "sqlite"], "projects": ["jarvis"]}
        cards = await run_discovery(sources=sources, user_context=ctx)
        assert len(cards) > 0

    @pytest.mark.asyncio
    async def test_install_candidate_found(self):
        c = Candidate(
            id="install-001", name="test-tool", pitch="A test tool",
            source="test", source_url=None, candidate_type="cli",
        )
        result = await install_candidate("install-001", {"install-001": c})
        assert result["status"] == "installed"
        assert result["name"] == "test-tool"

    @pytest.mark.asyncio
    async def test_install_candidate_not_found(self):
        result = await install_candidate("nonexistent", {})
        assert result["status"] == "error"
        assert "not found" in result["message"]


# ── Server endpoint tests ───────────────────────────────────────────────


class TestServerEndpoints:
    @pytest.mark.asyncio
    async def test_scout_sources_endpoint(self, client: httpx.AsyncClient):
        resp = await client.get("/scout/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert "count" in data
        assert isinstance(data["sources"], list)
        assert data["count"] == len(data["sources"])

    @pytest.mark.asyncio
    async def test_scout_sources_have_required_fields(self, client: httpx.AsyncClient):
        resp = await client.get("/scout/sources")
        data = resp.json()
        if data["sources"]:
            src = data["sources"][0]
            assert "name" in src
            assert "enabled" in src
            assert "cadence" in src
            assert "description" in src

    @pytest.mark.asyncio
    async def test_scout_discover_endpoint(self, client: httpx.AsyncClient):
        resp = await client.post("/scout/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert "finds" in data
        assert "scanned_at" in data
        assert isinstance(data["finds"], list)

    @pytest.mark.asyncio
    async def test_scout_install_endpoint(self, client: httpx.AsyncClient):
        resp = await client.post("/scout/install", json={"candidate_id": "test-999"})
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_scout_dismiss_endpoint(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/scout/dismiss",
            json={"candidate_id": "dismiss-001", "reason": "Not relevant"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"
        assert data["candidate_id"] == "dismiss-001"

    @pytest.mark.asyncio
    async def test_scout_dismiss_without_reason(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/scout/dismiss",
            json={"candidate_id": "dismiss-002"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_status_shows_scout_available(self, client: httpx.AsyncClient):
        resp = await client.get("/status")
        data = resp.json()
        assert data["services"]["scout"] == "available"
