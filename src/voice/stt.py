"""Speech-to-Text engine — multi-provider with local-first fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import toml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

STT_PROVIDERS = ["whisper_local", "openai_whisper", "deepgram", "macos_dictation"]


def _load_stt_config() -> dict:
    """Load STT config from voice.toml."""
    voice_path = CONFIG_DIR / "voice.toml"
    if not voice_path.exists():
        return {"provider": "macos_dictation", "fallback_threshold": 0.7}
    try:
        data = toml.load(voice_path)
        return data.get("stt", {"provider": "macos_dictation", "fallback_threshold": 0.7})
    except Exception:
        return {"provider": "macos_dictation", "fallback_threshold": 0.7}


@dataclass
class STTResult:
    """Result from a speech-to-text transcription."""

    text: str
    confidence: float
    source: str  # provider name
    duration_ms: int


async def _transcribe_whisper_local(
    audio_path: str,
    *,
    mock_confidence: float | None = None,
) -> STTResult:
    """Transcribe audio via local Whisper.cpp subprocess.

    Shells out to the whisper.cpp binary if installed.
    Falls back to macOS speech recognition if unavailable.
    """
    import shutil

    whisper_bin = shutil.which("whisper") or shutil.which("whisper.cpp") or shutil.which("whisper-cpp")
    if whisper_bin:
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                whisper_bin, "-f", audio_path, "--no-timestamps", "-nt",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            text = stdout.decode().strip()
            elapsed = int((time.monotonic() - start) * 1000)
            confidence = mock_confidence if mock_confidence is not None else 0.92
            return STTResult(text=text, confidence=confidence, source="whisper_local", duration_ms=elapsed)
        except Exception as e:
            logger.warning("Whisper.cpp failed: %s", e)

    # No whisper binary — return empty result so caller can fall back to cloud
    logger.info("Whisper.cpp not installed, returning empty STT result")
    return STTResult(text="", confidence=0.0, source="whisper_local", duration_ms=0)


async def _transcribe_openai_whisper(audio_path: str, config: dict) -> STTResult:
    """Transcribe audio via OpenAI Whisper API."""
    import httpx

    api_key = config.get("api_key", "")
    if not api_key:
        logger.warning("OpenAI Whisper API key not set — cannot transcribe")
        return STTResult(text="", confidence=0.0, source="openai_whisper", duration_ms=0)

    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as f:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": "whisper-1"},
                timeout=30,
            )
        resp.raise_for_status()
        data = resp.json()
    elapsed = int((time.monotonic() - start) * 1000)
    return STTResult(
        text=data.get("text", ""),
        confidence=0.97,
        source="openai_whisper",
        duration_ms=elapsed,
    )


async def _transcribe_deepgram(audio_path: str, config: dict) -> STTResult:
    """Transcribe audio via Deepgram API."""
    import httpx

    api_key = config.get("api_key", "")
    if not api_key:
        logger.warning("Deepgram API key not set — cannot transcribe")
        return STTResult(text="", confidence=0.0, source="deepgram", duration_ms=0)

    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        resp = await client.post(
            "https://api.deepgram.com/v1/listen",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/wav",
            },
            content=audio_data,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    elapsed = int((time.monotonic() - start) * 1000)
    alt = (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
    )
    return STTResult(
        text=alt.get("transcript", ""),
        confidence=alt.get("confidence", 0.0),
        source="deepgram",
        duration_ms=elapsed,
    )


async def _transcribe_macos_dictation(audio_path: str) -> STTResult:
    """Transcribe using macOS built-in speech recognition via SFSpeechRecognizer.

    Uses the `say` command's speech recognition counterpart via a small Python script
    that calls the macOS SFSpeechRecognizer framework. Falls back to empty on failure.
    """
    start = time.monotonic()
    try:
        # Use macOS `speech` CLI or Python objc bridge if available
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c",
            "import speech_recognition as sr; "
            "r = sr.Recognizer(); "
            f"a = sr.AudioFile('{audio_path}'); "
            "s = r.record(a); "
            "print(r.recognize_sphinx(s))",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        text = stdout.decode().strip()
        elapsed = int((time.monotonic() - start) * 1000)
        if text:
            return STTResult(text=text, confidence=0.85, source="macos_dictation", duration_ms=elapsed)
    except Exception as e:
        logger.debug("macOS dictation failed: %s", e)

    return STTResult(text="", confidence=0.0, source="macos_dictation", duration_ms=0)


async def transcribe(
    audio_path: str,
    *,
    fallback_threshold: float | None = None,
    mock_confidence: float | None = None,
    config: dict | None = None,
) -> STTResult:
    """Transcribe audio using the configured provider.

    For whisper_local: if confidence < fallback_threshold, retries with cloud.
    """
    cfg = config or _load_stt_config()
    provider = cfg.get("provider", "macos_dictation")
    threshold = fallback_threshold if fallback_threshold is not None else cfg.get("fallback_threshold", 0.7)

    start = time.monotonic()

    if provider == "whisper_local":
        result = await _transcribe_whisper_local(audio_path, mock_confidence=mock_confidence)
        if result.confidence < threshold:
            cloud_result = await _transcribe_openai_whisper(audio_path, cfg)
            cloud_result.duration_ms = int((time.monotonic() - start) * 1000)
            return cloud_result
        result.duration_ms = max(result.duration_ms, int((time.monotonic() - start) * 1000))
        return result

    elif provider == "openai_whisper":
        return await _transcribe_openai_whisper(audio_path, cfg)

    elif provider == "deepgram":
        return await _transcribe_deepgram(audio_path, cfg)

    elif provider == "macos_dictation":
        return await _transcribe_macos_dictation(audio_path)

    else:
        logger.warning("Unknown STT provider: %s", provider)
        return STTResult(text="", confidence=0.0, source=provider, duration_ms=0)


def is_whisper_installed() -> bool:
    """Check whether the whisper.cpp binary is available."""
    import shutil
    return shutil.which("whisper") is not None or shutil.which("whisper.cpp") is not None
