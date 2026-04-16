"""Jarvis MCP Core Daemon — FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.brain.router import classify, control_intent, local_intent
from src.briefing.composer import compose_briefing
from src.briefing.writer import write_to_obsidian
from src.hands.executor import execute_control
from src.scout.cards import card_to_dict
from src.scout.engine import install_candidate, run_discovery
from src.scout.signals import Signal, log_signal
from src.scout.sources import load_sources
from src.settings.dashboard import render_dashboard
from src.settings.manager import (
    export_all_data,
    load_all_settings,
    load_control_tiers,
    load_notifications,
    save_control_tiers,
    save_notifications,
    save_section,
    save_setting,
)
from src.setup.engine import (
    execute_step,
    get_setup_progress,
    is_setup_complete,
    skip_setup_step,
    start_setup,
)
from src.setup.steps import SetupState
from src.voice.activation import ActivationConfig, VoiceActivation
from src.voice.pipeline import voice_roundtrip
from src.voice.stt import transcribe
from src.voice.tts import generate_phrase_cache, synthesize

VERSION = "0.1.0"

_start_time: float = 0.0
_setup_state: SetupState | None = None
_voice_activation = VoiceActivation(ActivationConfig())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time
    _start_time = time.monotonic()
    yield


app = FastAPI(title="Jarvis MCP Core Daemon", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://127.0.0.1:*"],
    allow_origin_regex=r"^http://127\.0\.0\.1(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────────────

class RouteRequest(BaseModel):
    message: str


class RouteResponse(BaseModel):
    surface: str
    intent: dict[str, str | None] | None


class LessonProposeRequest(BaseModel):
    correction: str
    context: str


class ControlExecuteRequest(BaseModel):
    intent: dict[str, str | None]
    confirmed: bool = False


class ScoutInstallRequest(BaseModel):
    candidate_id: str


class ScoutDismissRequest(BaseModel):
    candidate_id: str
    reason: str | None = None


class SetupStepRequest(BaseModel):
    config: dict = {}


class VoiceTranscribeRequest(BaseModel):
    audio_path: str


class VoiceSynthesizeRequest(BaseModel):
    text: str


class VoicePipelineRequest(BaseModel):
    audio_path: str


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": VERSION,
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
    }


@app.get("/status")
async def status() -> dict[str, Any]:
    return {
        "daemon": "running",
        "services": {
            "router": "available",
            "briefing": "placeholder",
            "lessons": "placeholder",
            "scout": "available",
            "settings": "available",
            "voice": "available",
            "setup": "available",
        },
    }


@app.post("/route")
async def route(body: RouteRequest) -> RouteResponse:
    surface = classify(body.message)
    intent: dict[str, str] | None = None
    if surface.value == "control":
        intent = control_intent(body.message)
    elif surface.value == "local":
        handler = local_intent(body.message)
        if handler:
            intent = {"verb": handler, "target": None, "payload": None}
    return RouteResponse(surface=surface.value.upper(), intent=intent)


@app.post("/control/execute")
async def control_execute(body: ControlExecuteRequest) -> dict[str, Any]:
    result = await execute_control(body.intent, confirmed=body.confirmed)
    return {
        "success": result.success,
        "message": result.message,
        "action": result.action,
        "confirmed": result.confirmed,
    }


@app.post("/control/confirm")
async def control_confirm(body: ControlExecuteRequest) -> dict[str, Any]:
    result = await execute_control(body.intent, confirmed=True)
    return {
        "success": result.success,
        "message": result.message,
        "action": result.action,
        "confirmed": result.confirmed,
    }


@app.get("/briefing")
async def briefing() -> dict[str, Any]:
    result = await compose_briefing()
    return {
        "sections": [asdict(s) for s in result.sections],
        "generated_at": result.generated_at,
        "summary": result.summary,
    }


@app.get("/briefing/obsidian")
async def briefing_obsidian(vault_path: str = Query(...)) -> dict[str, str]:
    result = await compose_briefing()
    file_path = write_to_obsidian(result, vault_path)
    return {"file_path": file_path}


@app.get("/lessons")
async def lessons_list() -> dict[str, Any]:
    return {"lessons": [], "count": 0}


@app.post("/lessons/propose")
async def lessons_propose(body: LessonProposeRequest) -> dict[str, str]:
    return {
        "draft": f"Proposed lesson from correction: {body.correction}",
        "status": "pending_approval",
    }


@app.get("/scout/sources")
async def scout_sources() -> dict[str, Any]:
    sources = load_sources()
    return {
        "sources": [
            {
                "name": s.name,
                "enabled": s.enabled,
                "cadence": s.cadence,
                "description": s.description,
            }
            for s in sources
        ],
        "count": len(sources),
    }


@app.post("/scout/discover")
async def scout_discover() -> dict[str, Any]:
    cards = await run_discovery()
    return {
        "finds": [card_to_dict(c) for c in cards],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/scout/install")
async def scout_install(body: ScoutInstallRequest) -> dict[str, Any]:
    # In v1 we don't maintain a persistent candidate store, so mock it
    result = await install_candidate(body.candidate_id, {})
    return result


@app.post("/scout/dismiss")
async def scout_dismiss(body: ScoutDismissRequest) -> dict[str, str]:
    signal = Signal(
        candidate_id=body.candidate_id,
        action="dismissed",
        reason=body.reason,
    )
    log_signal(signal)
    return {"status": "dismissed", "candidate_id": body.candidate_id}


@app.get("/settings")
async def settings() -> dict[str, Any]:
    return load_all_settings()


@app.get("/settings/dashboard", response_class=HTMLResponse)
async def settings_dashboard() -> HTMLResponse:
    all_settings = load_all_settings()
    html = render_dashboard(all_settings)
    return HTMLResponse(content=html)


@app.get("/settings/notifications")
async def settings_notifications_get() -> dict[str, Any]:
    return load_notifications()


@app.put("/settings/notifications")
async def settings_notifications_put(body: dict[str, Any]) -> dict[str, Any]:
    ok = save_notifications(body)
    return {"success": ok}


@app.get("/settings/control-tiers")
async def settings_control_tiers_get() -> dict[str, Any]:
    return load_control_tiers()


@app.put("/settings/control-tiers")
async def settings_control_tiers_put(body: dict[str, Any]) -> dict[str, Any]:
    ok = save_control_tiers(body)
    return {"success": ok}


@app.post("/settings/export")
async def settings_export() -> dict[str, str]:
    path = export_all_data("")
    return {"path": path}


@app.put("/settings/{section_name}")
async def settings_update_section(section_name: str, body: dict[str, Any]) -> dict[str, Any]:
    ok = save_section(section_name, body)
    if not ok:
        return {"success": False, "error": f"Unknown section: {section_name}"}
    return {"success": True, "section": section_name}


@app.put("/settings/{section_name}/{key}")
async def settings_update_key(
    section_name: str, key: str, body: dict[str, Any]
) -> dict[str, Any]:
    value = body.get("value")
    ok = save_setting(section_name, key, value)
    if not ok:
        return {"success": False, "error": f"Unknown section: {section_name}"}
    return {"success": True, "section": section_name, "key": key}


# ── Voice endpoints ─────────────────────────────────────────────────

@app.post("/voice/transcribe")
async def voice_transcribe(body: VoiceTranscribeRequest) -> dict[str, Any]:
    result = await transcribe(body.audio_path)
    return {
        "text": result.text,
        "confidence": result.confidence,
        "source": result.source,
        "duration_ms": result.duration_ms,
    }


@app.post("/voice/synthesize")
async def voice_synthesize(body: VoiceSynthesizeRequest) -> dict[str, Any]:
    result = await synthesize(body.text)
    return {
        "audio_path": result.audio_path,
        "text": result.text,
        "source": result.source,
        "duration_ms": result.duration_ms,
    }


@app.get("/voice/status")
async def voice_status() -> dict[str, Any]:
    return _voice_activation.get_status()


@app.post("/voice/pipeline")
async def voice_pipeline(body: VoicePipelineRequest) -> dict[str, Any]:
    result = await voice_roundtrip(body.audio_path)
    return {
        "transcription": {
            "text": result.transcription.text,
            "confidence": result.transcription.confidence,
            "source": result.transcription.source,
            "duration_ms": result.transcription.duration_ms,
        },
        "response_text": result.response_text,
        "tts": {
            "audio_path": result.tts.audio_path,
            "text": result.tts.text,
            "source": result.tts.source,
            "duration_ms": result.tts.duration_ms,
        } if result.tts else None,
        "total_ms": result.total_ms,
    }


@app.post("/voice/cache/generate")
async def voice_cache_generate() -> dict[str, Any]:
    count = await generate_phrase_cache()
    return {"generated": count}


# ── Setup endpoints ──────────────────────────────────────────────────

@app.post("/setup/start")
async def setup_start() -> dict[str, Any]:
    global _setup_state
    _setup_state = await start_setup()
    return {
        "status": "started",
        "current_step": _setup_state.current_step,
        "total_steps": len(_setup_state.steps),
        "started_at": _setup_state.started_at,
    }


@app.post("/setup/step/{step_number}")
async def setup_step(step_number: int, body: SetupStepRequest) -> dict[str, Any]:
    global _setup_state
    if _setup_state is None:
        return {"error": "Setup not started. Call POST /setup/start first."}
    _setup_state, result = await execute_step(_setup_state, step_number, body.config)
    return {
        "step": step_number,
        "result": result,
        "current_step": _setup_state.current_step,
        "complete": is_setup_complete(_setup_state),
    }


@app.post("/setup/skip/{step_number}")
async def setup_skip(step_number: int) -> dict[str, Any]:
    global _setup_state
    if _setup_state is None:
        return {"error": "Setup not started. Call POST /setup/start first."}
    try:
        _setup_state, result = await skip_setup_step(_setup_state, step_number)
        return {"step": step_number, "result": result}
    except ValueError as exc:
        return {"error": str(exc)}


@app.get("/setup/progress")
async def setup_progress() -> dict[str, Any]:
    global _setup_state
    if _setup_state is None:
        return {"error": "Setup not started. Call POST /setup/start first."}
    return get_setup_progress(_setup_state)
