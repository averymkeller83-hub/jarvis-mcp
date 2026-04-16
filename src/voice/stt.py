"""Speech-to-Text engine — Whisper.cpp local-first with cloud fallback."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class STTResult:
    """Result from a speech-to-text transcription."""

    text: str
    confidence: float
    source: str  # "local" | "cloud"
    duration_ms: int


async def transcribe_whisper_local(
    audio_path: str,
    *,
    mock_confidence: float | None = None,
) -> STTResult:
    """Transcribe audio via local Whisper.cpp subprocess (mocked).

    In production this would shell out to the whisper.cpp binary.
    For now, returns deterministic mock data.
    """
    confidence = mock_confidence if mock_confidence is not None else 0.92
    return STTResult(
        text="Hello Jarvis",
        confidence=confidence,
        source="local",
        duration_ms=850,
    )


async def transcribe_whisper_cloud(audio_path: str) -> STTResult:
    """Transcribe audio via OpenAI Whisper API (mocked).

    In production this would hit the OpenAI Whisper endpoint.
    Only called when local confidence is below threshold.
    """
    return STTResult(
        text="Hello Jarvis",
        confidence=0.97,
        source="cloud",
        duration_ms=1200,
    )


async def transcribe(
    audio_path: str,
    *,
    fallback_threshold: float = 0.7,
    mock_confidence: float | None = None,
) -> STTResult:
    """Transcribe audio with local-first strategy and cloud fallback.

    1. Attempt local Whisper.cpp transcription.
    2. If confidence < fallback_threshold, re-send to cloud Whisper API.
    Audio never leaves the machine unless the fallback fires.
    """
    start = time.monotonic()
    local_result = await transcribe_whisper_local(
        audio_path, mock_confidence=mock_confidence
    )

    if local_result.confidence < fallback_threshold:
        cloud_result = await transcribe_whisper_cloud(audio_path)
        elapsed = int((time.monotonic() - start) * 1000)
        cloud_result.duration_ms = elapsed
        return cloud_result

    elapsed = int((time.monotonic() - start) * 1000)
    local_result.duration_ms = max(local_result.duration_ms, elapsed)
    return local_result


def is_whisper_installed() -> bool:
    """Check whether the whisper.cpp binary is available (mocked → True)."""
    return True
