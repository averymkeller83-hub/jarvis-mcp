"""End-to-end voice pipeline — mic -> STT -> router -> TTS -> speaker."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from src.voice.stt import STTResult, transcribe
from src.voice.tts import TTSResult, synthesize


async def _echo(text: str) -> str:
    """Default process function — echoes the input back."""
    return text


@dataclass
class VoicePipelineResult:
    """Full result from a voice round-trip."""

    transcription: STTResult
    response_text: str
    tts: TTSResult | None
    total_ms: int


async def voice_roundtrip(
    audio_path: str,
    process_fn: Callable[[str], Coroutine[Any, Any, str]] | None = None,
    user_name: str = "Sir",
    cache_dir: str = "cache/tts",
) -> VoicePipelineResult:
    """Run the full voice pipeline: STT -> process -> TTS.

    Parameters
    ----------
    audio_path:
        Path to the input audio file.
    process_fn:
        Async callable that takes the transcribed text and returns a
        response string.  Defaults to an echo function for testing.
    user_name:
        Name to inject into TTS template phrases.
    cache_dir:
        Directory for TTS audio cache.

    Returns
    -------
    VoicePipelineResult with transcription, response text, TTS result,
    and total elapsed time in milliseconds.
    """
    start = time.monotonic()
    fn = process_fn or _echo

    # Step 1: Speech-to-Text
    stt_result = await transcribe(audio_path)

    # Step 2: Process (router / Claude / echo)
    response_text = await fn(stt_result.text)

    # Step 3: Text-to-Speech
    tts_result = await synthesize(response_text, cache_dir=cache_dir, user_name=user_name)

    total_ms = int((time.monotonic() - start) * 1000)

    return VoicePipelineResult(
        transcription=stt_result,
        response_text=response_text,
        tts=tts_result,
        total_ms=total_ms,
    )
