"""Comprehensive tests for the Jarvis Voice pipeline module."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from src.server.app import app
from src.voice.activation import ActivationConfig, VoiceActivation
from src.voice.pipeline import VoicePipelineResult, voice_roundtrip
from src.voice.stt import (
    STTResult,
    is_whisper_installed,
    transcribe,
    transcribe_whisper_cloud,
    transcribe_whisper_local,
)
from src.voice.tts import (
    COMMON_PHRASES,
    TTSResult,
    generate_phrase_cache,
    get_cache_path,
    invalidate_cache,
    is_cached,
    synthesize,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


# ── STT tests ────────────────────────────────────────────────────────


async def test_stt_local_transcription_returns_valid_result():
    result = await transcribe_whisper_local("test.wav")
    assert isinstance(result, STTResult)
    assert result.text == "Hello Jarvis"
    assert result.source == "local"
    assert result.confidence > 0
    assert result.duration_ms > 0


async def test_stt_cloud_transcription_returns_valid_result():
    result = await transcribe_whisper_cloud("test.wav")
    assert isinstance(result, STTResult)
    assert result.text == "Hello Jarvis"
    assert result.source == "cloud"
    assert result.confidence >= 0.95


async def test_stt_cloud_fallback_fires_when_confidence_low():
    result = await transcribe("test.wav", mock_confidence=0.3)
    assert result.source == "cloud"
    assert result.confidence >= 0.95


async def test_stt_stays_local_when_confidence_high():
    result = await transcribe("test.wav", mock_confidence=0.95)
    assert result.source == "local"
    assert result.confidence == 0.95


async def test_stt_fallback_at_exact_threshold():
    # Confidence == threshold should NOT fallback (only strictly less than)
    result = await transcribe("test.wav", fallback_threshold=0.7, mock_confidence=0.7)
    assert result.source == "local"


async def test_stt_fallback_just_below_threshold():
    result = await transcribe("test.wav", fallback_threshold=0.7, mock_confidence=0.69)
    assert result.source == "cloud"


async def test_stt_default_confidence_stays_local():
    # Default mock confidence is 0.92, well above 0.7 threshold
    result = await transcribe("test.wav")
    assert result.source == "local"
    assert result.confidence == 0.92


async def test_is_whisper_installed():
    assert is_whisper_installed() is True


# ── TTS tests ────────────────────────────────────────────────────────


async def test_tts_cache_miss_calls_api(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    result = await synthesize("Hello there", cache_dir=cache_dir)
    assert isinstance(result, TTSResult)
    assert result.source == "api"
    assert result.text == "Hello there"
    assert Path(result.audio_path).exists()


async def test_tts_cache_hit_returns_cached(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    # First call — cache miss
    first = await synthesize("Greetings", cache_dir=cache_dir)
    assert first.source == "api"
    # Second call — cache hit
    second = await synthesize("Greetings", cache_dir=cache_dir)
    assert second.source == "cache"
    assert second.audio_path == first.audio_path


async def test_tts_template_variable_expansion(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    result = await synthesize(
        "Good morning, {user_name}.", cache_dir=cache_dir, user_name="Avery"
    )
    assert result.text == "Good morning, Avery."
    assert "{user_name}" not in result.text


async def test_tts_template_time_expansion(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    result = await synthesize(
        "Alarm set for {time}.", cache_dir=cache_dir, user_name="Sir"
    )
    assert result.text == "Alarm set for 7 AM."


async def test_get_cache_path_is_deterministic():
    path_a = get_cache_path("hello world")
    path_b = get_cache_path("hello world")
    assert path_a == path_b


async def test_get_cache_path_differs_for_different_text():
    path_a = get_cache_path("hello")
    path_b = get_cache_path("goodbye")
    assert path_a != path_b


async def test_get_cache_path_uses_cache_dir():
    path = get_cache_path("test", cache_dir="/my/custom/dir")
    assert path.startswith("/my/custom/dir/")
    assert path.endswith(".wav")


async def test_is_cached_false_for_missing(tmp_path: Path):
    assert is_cached("nonexistent text", cache_dir=str(tmp_path)) is False


async def test_is_cached_true_after_synthesize(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    await synthesize("cached phrase", cache_dir=cache_dir)
    assert is_cached("cached phrase", cache_dir=cache_dir) is True


async def test_phrase_cache_generation(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    count = await generate_phrase_cache(user_name="Avery", cache_dir=cache_dir)
    assert count == len(COMMON_PHRASES)
    # All phrases should now be cached
    wav_files = list(Path(cache_dir).glob("*.wav"))
    assert len(wav_files) == len(COMMON_PHRASES)


async def test_phrase_cache_generation_skips_existing(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    first = await generate_phrase_cache(user_name="Sir", cache_dir=cache_dir)
    second = await generate_phrase_cache(user_name="Sir", cache_dir=cache_dir)
    assert first == len(COMMON_PHRASES)
    assert second == 0  # All already cached


async def test_cache_invalidation(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    await generate_phrase_cache(user_name="Sir", cache_dir=cache_dir)
    removed = invalidate_cache(cache_dir=cache_dir)
    assert removed == len(COMMON_PHRASES)
    wav_files = list(Path(cache_dir).glob("*.wav"))
    assert len(wav_files) == 0


async def test_cache_invalidation_empty_dir(tmp_path: Path):
    cache_dir = str(tmp_path / "empty_cache")
    removed = invalidate_cache(cache_dir=cache_dir)
    assert removed == 0


# ── Activation tests ─────────────────────────────────────────────────


def test_activation_default_config():
    config = ActivationConfig()
    assert config.hotkey == "alt+space"
    assert config.wake_word_enabled is False
    assert config.wake_word_phrase == "hey jarvis"
    assert config.listening is False


def test_activation_start_stop_listening():
    va = VoiceActivation()
    assert va.is_listening() is False
    assert va.start_listening() is True
    assert va.is_listening() is True
    assert va.stop_listening() is True
    assert va.is_listening() is False


def test_activation_status():
    config = ActivationConfig(hotkey="ctrl+shift+j", wake_word_enabled=True)
    va = VoiceActivation(config)
    status = va.get_status()
    assert status["hotkey"] == "ctrl+shift+j"
    assert status["wake_word_enabled"] is True
    assert status["wake_word_phrase"] == "hey jarvis"
    assert status["listening"] is False


def test_activation_update_wake_word():
    va = VoiceActivation()
    va.update_wake_word("  Hey Friday  ")
    status = va.get_status()
    assert status["wake_word_phrase"] == "hey friday"


def test_activation_custom_config():
    config = ActivationConfig(
        hotkey="cmd+space",
        wake_word_enabled=True,
        wake_word_phrase="computer",
    )
    va = VoiceActivation(config)
    status = va.get_status()
    assert status["hotkey"] == "cmd+space"
    assert status["wake_word_phrase"] == "computer"


# ── Pipeline tests ───────────────────────────────────────────────────


async def test_pipeline_end_to_end(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    result = await voice_roundtrip("test.wav", cache_dir=cache_dir)
    assert isinstance(result, VoicePipelineResult)
    assert isinstance(result.transcription, STTResult)
    assert isinstance(result.tts, TTSResult)
    assert result.response_text == result.transcription.text  # echo


async def test_pipeline_with_custom_process_fn(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")

    async def uppercase(text: str) -> str:
        return text.upper()

    result = await voice_roundtrip("test.wav", process_fn=uppercase, cache_dir=cache_dir)
    assert result.response_text == "HELLO JARVIS"


async def test_pipeline_timing_is_tracked(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")
    result = await voice_roundtrip("test.wav", cache_dir=cache_dir)
    assert result.total_ms >= 0


async def test_pipeline_uses_user_name(tmp_path: Path):
    cache_dir = str(tmp_path / "tts_cache")

    async def greet(text: str) -> str:
        return "Good morning, {user_name}."

    result = await voice_roundtrip(
        "test.wav", process_fn=greet, user_name="Avery", cache_dir=cache_dir
    )
    assert result.tts is not None
    assert result.tts.text == "Good morning, Avery."


# ── Server endpoint tests ───────────────────────────────────────────


async def test_server_voice_transcribe(client: httpx.AsyncClient):
    resp = await client.post("/voice/transcribe", json={"audio_path": "test.wav"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Hello Jarvis"
    assert data["source"] in ("local", "cloud")
    assert "confidence" in data
    assert "duration_ms" in data


async def test_server_voice_synthesize(client: httpx.AsyncClient):
    resp = await client.post("/voice/synthesize", json={"text": "Done."})
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Done."
    assert data["source"] in ("cache", "api")
    assert "audio_path" in data


async def test_server_voice_status(client: httpx.AsyncClient):
    resp = await client.get("/voice/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "hotkey" in data
    assert "wake_word_enabled" in data
    assert "listening" in data


async def test_server_voice_pipeline(client: httpx.AsyncClient):
    resp = await client.post("/voice/pipeline", json={"audio_path": "test.wav"})
    assert resp.status_code == 200
    data = resp.json()
    assert "transcription" in data
    assert "response_text" in data
    assert "tts" in data
    assert "total_ms" in data
    assert data["transcription"]["text"] == "Hello Jarvis"


async def test_server_voice_cache_generate(client: httpx.AsyncClient):
    resp = await client.post("/voice/cache/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert "generated" in data
    assert isinstance(data["generated"], int)


async def test_server_status_includes_voice(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["voice"] == "available"


# ── Additional edge-case tests ──────────────────────────────────────


async def test_stt_result_dataclass_fields():
    result = STTResult(text="hi", confidence=0.5, source="local", duration_ms=100)
    assert result.text == "hi"
    assert result.confidence == 0.5
    assert result.source == "local"
    assert result.duration_ms == 100


async def test_tts_result_dataclass_fields():
    result = TTSResult(audio_path="/tmp/a.wav", text="hi", source="cache", duration_ms=0)
    assert result.audio_path == "/tmp/a.wav"
    assert result.source == "cache"


async def test_tts_synthesize_creates_cache_dir(tmp_path: Path):
    deep = str(tmp_path / "a" / "b" / "c")
    result = await synthesize("test", cache_dir=deep)
    assert Path(deep).exists()
    assert result.source == "api"


async def test_tts_common_phrases_has_at_least_30():
    assert len(COMMON_PHRASES) >= 30


async def test_pipeline_echo_default(tmp_path: Path):
    cache_dir = str(tmp_path / "tts")
    result = await voice_roundtrip("test.wav", cache_dir=cache_dir)
    # Default process_fn is echo, so response == transcription
    assert result.response_text == result.transcription.text


async def test_pipeline_tts_audio_file_exists(tmp_path: Path):
    cache_dir = str(tmp_path / "tts")
    result = await voice_roundtrip("test.wav", cache_dir=cache_dir)
    assert result.tts is not None
    assert Path(result.tts.audio_path).exists()


def test_activation_listening_state_isolation():
    """Two VoiceActivation instances don't share state."""
    va1 = VoiceActivation()
    va2 = VoiceActivation()
    va1.start_listening()
    assert va1.is_listening() is True
    assert va2.is_listening() is False


async def test_tts_cache_path_ends_with_wav():
    path = get_cache_path("anything at all")
    assert path.endswith(".wav")


async def test_server_voice_transcribe_returns_confidence(client: httpx.AsyncClient):
    resp = await client.post("/voice/transcribe", json={"audio_path": "x.wav"})
    data = resp.json()
    assert 0 <= data["confidence"] <= 1.0


async def test_server_voice_pipeline_has_tts_fields(client: httpx.AsyncClient):
    resp = await client.post("/voice/pipeline", json={"audio_path": "test.wav"})
    data = resp.json()
    tts = data["tts"]
    assert "audio_path" in tts
    assert "text" in tts
    assert "source" in tts
    assert "duration_ms" in tts
