"""Tests for multi-provider TTS and STT."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.voice.tts import (
    TTS_PROVIDERS,
    TTSResult,
    _load_tts_config,
    get_cache_path,
    invalidate_cache,
    is_cached,
    synthesize,
)
from src.voice.stt import (
    STT_PROVIDERS,
    STTResult,
    _load_stt_config,
    transcribe,
)


class TestTTSProviderList:
    def test_all_providers_listed(self):
        assert "fish_audio" in TTS_PROVIDERS
        assert "claude_tts" in TTS_PROVIDERS
        assert "elevenlabs" in TTS_PROVIDERS
        assert "openai_tts" in TTS_PROVIDERS
        assert "macos_say" in TTS_PROVIDERS


class TestTTSConfig:
    def test_default_config_no_file(self):
        with patch("src.voice.tts.CONFIG_DIR", Path("/nonexistent")):
            cfg = _load_tts_config()
            assert cfg["provider"] == "macos_say"


class TestTTSCache:
    def test_cache_path_deterministic(self):
        p1 = get_cache_path("hello")
        p2 = get_cache_path("hello")
        assert p1 == p2

    def test_cache_path_differs_for_different_text(self):
        p1 = get_cache_path("hello")
        p2 = get_cache_path("world")
        assert p1 != p2

    def test_is_cached_false(self):
        assert is_cached("nonexistent_text_12345", "/tmp/no_such_dir") is False


class TestTTSSynthesize:
    @pytest.mark.asyncio
    async def test_synthesize_macos_say(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("src.voice.tts._synth_macos_say", new_callable=AsyncMock) as mock_say:
                async def write_mock(text, path):
                    Path(path).write_bytes(b"AUDIO")
                mock_say.side_effect = write_mock

                result = await synthesize(
                    "Hello",
                    cache_dir=td,
                    config={"provider": "macos_say"},
                )
                assert result.source == "macos_say"
                assert result.text == "Hello"
                mock_say.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            # Pre-populate cache
            cache_path = get_cache_path("Hello", td)
            Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
            Path(cache_path).write_bytes(b"CACHED")

            result = await synthesize(
                "Hello",
                cache_dir=td,
                config={"provider": "macos_say"},
            )
            assert result.source == "cache"
            assert result.duration_ms == 0

    @pytest.mark.asyncio
    async def test_synthesize_fish_audio_no_key(self):
        with tempfile.TemporaryDirectory() as td:
            result = await synthesize(
                "Test",
                cache_dir=td,
                config={"provider": "fish_audio"},  # no api_key
            )
            assert result.source == "fish_audio"
            assert Path(result.audio_path).exists()

    @pytest.mark.asyncio
    async def test_synthesize_unknown_provider(self):
        with tempfile.TemporaryDirectory() as td:
            result = await synthesize(
                "Test",
                cache_dir=td,
                config={"provider": "unknown_provider"},
            )
            assert result.source == "unknown_provider"

    def test_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "a.wav").write_bytes(b"x")
            Path(td, "b.wav").write_bytes(b"y")
            removed = invalidate_cache(td)
            assert removed == 2

    def test_invalidate_empty_cache(self):
        removed = invalidate_cache("/tmp/no_such_cache_dir_12345")
        assert removed == 0


class TestSTTProviderList:
    def test_all_providers_listed(self):
        assert "whisper_local" in STT_PROVIDERS
        assert "openai_whisper" in STT_PROVIDERS
        assert "deepgram" in STT_PROVIDERS
        assert "macos_dictation" in STT_PROVIDERS


class TestSTTConfig:
    def test_default_config_no_file(self):
        with patch("src.voice.stt.CONFIG_DIR", Path("/nonexistent")):
            cfg = _load_stt_config()
            assert cfg["provider"] == "macos_dictation"


class TestSTTTranscribe:
    @pytest.mark.asyncio
    async def test_transcribe_whisper_local(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "whisper_local", "fallback_threshold": 0.7},
            mock_confidence=0.95,
        )
        assert result.source == "whisper_local"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_transcribe_whisper_local_fallback(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "whisper_local", "fallback_threshold": 0.7},
            mock_confidence=0.3,  # below threshold
        )
        # Should fall back to openai_whisper (mocked since no API key)
        assert result.source == "openai_whisper"

    @pytest.mark.asyncio
    async def test_transcribe_macos_dictation(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "macos_dictation"},
        )
        assert result.source == "macos_dictation"

    @pytest.mark.asyncio
    async def test_transcribe_openai_whisper_no_key(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "openai_whisper"},  # no api_key
        )
        assert result.source == "openai_whisper"
        assert result.text == "Hello Jarvis"  # mock fallback

    @pytest.mark.asyncio
    async def test_transcribe_deepgram_no_key(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "deepgram"},  # no api_key
        )
        assert result.source == "deepgram"

    @pytest.mark.asyncio
    async def test_transcribe_unknown_provider(self):
        result = await transcribe(
            "/tmp/test.wav",
            config={"provider": "magic_ears"},
        )
        assert result.text == ""
        assert result.confidence == 0.0
