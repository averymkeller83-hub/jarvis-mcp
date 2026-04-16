"""Jarvis MCP Core Daemon — FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.brain.router import classify, control_intent, local_intent
from src.briefing.composer import compose_briefing
from src.briefing.writer import write_to_obsidian
from src.engine.scheduler import ProactiveEngine
from src.engine.tasks import register_default_tasks
from src.hands.executor import execute_control
from src.scout.cards import card_to_dict
from src.scout.engine import install_candidate, run_discovery
from src.scout.signals import Signal, log_signal
from src.scout.sources import load_sources
from src.settings.dashboard import render_dashboard
from src.briefing.news_sources import get_catalog, get_rss_urls_for_enabled
from src.settings.manager import (
    export_all_data,
    load_all_settings,
    load_control_tiers,
    load_news_sources,
    load_notifications,
    save_control_tiers,
    save_news_sources,
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
from src.sdk.manager import AgentManager
from src.auth.routes import router as auth_router
from src.voice.activation import ActivationConfig, VoiceActivation
from src.voice.pipeline import voice_roundtrip
from src.voice.stt import transcribe
from src.voice.tts import generate_phrase_cache, synthesize

VERSION = "0.1.0"

_start_time: float = 0.0
_setup_state: SetupState | None = None
_voice_activation = VoiceActivation(ActivationConfig())
_engine = ProactiveEngine()
_agent_manager: AgentManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time, _agent_manager
    _start_time = time.monotonic()
    register_default_tasks(_engine)

    # Initialize agent manager
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    _agent_manager = AgentManager(
        engine=_engine,
        config_dir=project_root / "config",
        builtin_dir=project_root / "src" / "agents",
        user_dir=project_root / "agents",
    )
    await _agent_manager.discover_and_register()

    await _engine.start()
    yield
    await _engine.stop()


app = FastAPI(title="Jarvis MCP Core Daemon", version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://127.0.0.1:*"],
    allow_origin_regex=r"^http://127\.0\.0\.1(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


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
    agent_info = {}
    if _agent_manager is not None:
        listing = _agent_manager.list_agents()
        running = sum(1 for a in listing if a["status"] == "running")
        pending = sum(1 for a in listing if a["status"] == "pending")
        agent_info = {
            "agents": "available",
            "agent_count": len(listing),
            "agents_running": running,
            "agents_pending": pending,
        }
    else:
        agent_info = {"agents": "unavailable"}

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
            "engine": "available",
            **agent_info,
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
    # Read news source config and resolve to RSS URLs + HN flag
    news_cfg = load_news_sources()
    enabled = news_cfg.get("enabled", ["hackernews"])
    rss_urls, hn_enabled = get_rss_urls_for_enabled(enabled)

    result = await compose_briefing({
        "rss_urls": rss_urls,
        "hn_enabled": hn_enabled,
        "hn_limit": news_cfg.get("hn_limit", 5),
        "hn_min_score": news_cfg.get("hn_min_score", 100),
    })
    return {
        "sections": [asdict(s) for s in result.sections],
        "generated_at": result.generated_at,
        "summary": result.summary,
    }


@app.get("/briefing/obsidian")
async def briefing_obsidian(vault_path: str = Query(...)) -> dict[str, str]:
    news_cfg = load_news_sources()
    enabled = news_cfg.get("enabled", ["hackernews"])
    rss_urls, hn_enabled = get_rss_urls_for_enabled(enabled)

    result = await compose_briefing({
        "rss_urls": rss_urls,
        "hn_enabled": hn_enabled,
        "hn_limit": news_cfg.get("hn_limit", 5),
        "hn_min_score": news_cfg.get("hn_min_score", 100),
    })
    file_path = write_to_obsidian(result, vault_path)
    return {"file_path": file_path}


@app.get("/news/catalog")
async def news_catalog() -> dict[str, Any]:
    """Return all available news sources and which ones are enabled."""
    catalog = get_catalog()
    cfg = load_news_sources()
    enabled = cfg.get("enabled", ["hackernews"])
    for item in catalog:
        item["enabled"] = item["id"] in enabled
    return {"sources": catalog, "count": len(catalog)}


@app.put("/news/sources")
async def news_sources_update(body: dict[str, Any]) -> dict[str, Any]:
    """Update which news sources are enabled."""
    ok = save_news_sources(body)
    return {"success": ok}


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
    from fastapi.responses import JSONResponse

    ok = save_section(section_name, body)
    if not ok:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Unknown section: {section_name}"},
        )
    return {"success": True, "section": section_name}


@app.put("/settings/{section_name}/{key}")
async def settings_update_key(
    section_name: str, key: str, body: dict[str, Any]
) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    value = body.get("value")
    ok = save_setting(section_name, key, value)
    if not ok:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"Unknown section: {section_name}"},
        )
    return {"success": True, "section": section_name, "key": key}


# ── Engine endpoints ────────────────────────────────────────────────

@app.get("/engine/schedule")
async def engine_schedule() -> dict[str, Any]:
    return {"tasks": _engine.get_schedule()}


@app.post("/engine/run/{task_name}")
async def engine_run_task(task_name: str) -> dict[str, Any]:
    result = await _engine.run_task(task_name)
    return result


@app.get("/engine/status")
async def engine_status() -> dict[str, Any]:
    return {
        "running": _engine.running,
        "task_count": len(_engine.get_schedule()),
    }


@app.post("/engine/start")
async def engine_start() -> dict[str, str]:
    await _engine.start()
    return {"status": "started"}


@app.post("/engine/stop")
async def engine_stop() -> dict[str, str]:
    await _engine.stop()
    return {"status": "stopped"}


# ── Agent endpoints ────────────────────────────────────────────────


class AgentRunRequest(BaseModel):
    params: dict = {}


@app.get("/agents")
async def agents_list() -> dict[str, Any]:
    if _agent_manager is None:
        return {"agents": [], "count": 0}
    listing = _agent_manager.list_agents()
    return {"agents": listing, "count": len(listing)}


@app.get("/agents/{name}")
async def agents_detail(name: str) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    if _agent_manager is None:
        return JSONResponse(status_code=404, content={"error": "Agent manager not initialized"})
    detail = _agent_manager.get_agent(name)
    if detail is None:
        return JSONResponse(status_code=404, content={"error": f"Agent '{name}' not found"})
    return detail


@app.post("/agents/{name}/run")
async def agents_run(name: str, body: AgentRunRequest) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    if _agent_manager is None:
        return JSONResponse(status_code=503, content={"error": "Agent manager not initialized"})
    result = await _agent_manager.invoke(name, body.params)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.put("/agents/{name}/approve")
async def agents_approve(name: str) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    if _agent_manager is None:
        return JSONResponse(status_code=503, content={"error": "Agent manager not initialized"})
    await _agent_manager.approve(name)
    return {"success": True, "agent": name, "status": "running"}


@app.post("/agents/{name}/stop")
async def agents_stop(name: str) -> dict[str, Any]:
    if _agent_manager is None:
        return {"error": "Agent manager not initialized"}
    await _agent_manager.stop_agent(name)
    return {"success": True, "agent": name, "status": "stopped"}


@app.post("/agents/{name}/start")
async def agents_start(name: str) -> dict[str, Any]:
    if _agent_manager is None:
        return {"error": "Agent manager not initialized"}
    await _agent_manager.start_agent(name)
    return {"success": True, "agent": name, "status": "running"}


@app.get("/agents/{name}/context")
async def agents_context(name: str) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    if _agent_manager is None:
        return JSONResponse(status_code=503, content={"error": "Agent manager not initialized"})
    agent = _agent_manager.agents.get(name)
    if agent is None:
        return JSONResponse(status_code=404, content={"error": f"Agent '{name}' not found"})
    keys = await _agent_manager._context.list(prefix=f"{name}.")
    data = {}
    for key in keys:
        data[key] = await _agent_manager._context.get(key)
    return data


@app.get("/events")
async def events_list() -> dict[str, Any]:
    if _agent_manager is None:
        return {"subscriptions": {}}
    return {"subscriptions": _agent_manager.event_bus.list_subscriptions()}


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


# ── API-prefixed routes (mirrors of legacy routes) ─────────────────

api_router = APIRouter(prefix="/api")

api_router.add_api_route("/health", health, methods=["GET"])
api_router.add_api_route("/status", status, methods=["GET"])
api_router.add_api_route("/route", route, methods=["POST"])
api_router.add_api_route("/control/execute", control_execute, methods=["POST"])
api_router.add_api_route("/control/confirm", control_confirm, methods=["POST"])
api_router.add_api_route("/briefing", briefing, methods=["GET"])
api_router.add_api_route("/briefing/obsidian", briefing_obsidian, methods=["GET"])
api_router.add_api_route("/news/catalog", news_catalog, methods=["GET"])
api_router.add_api_route("/news/sources", news_sources_update, methods=["PUT"])
api_router.add_api_route("/lessons", lessons_list, methods=["GET"])
api_router.add_api_route("/lessons/propose", lessons_propose, methods=["POST"])
api_router.add_api_route("/scout/sources", scout_sources, methods=["GET"])
api_router.add_api_route("/scout/discover", scout_discover, methods=["POST"])
api_router.add_api_route("/scout/install", scout_install, methods=["POST"])
api_router.add_api_route("/scout/dismiss", scout_dismiss, methods=["POST"])
api_router.add_api_route("/settings", settings, methods=["GET"])
api_router.add_api_route("/settings/dashboard", settings_dashboard, methods=["GET"])
api_router.add_api_route("/settings/notifications", settings_notifications_get, methods=["GET"])
api_router.add_api_route("/settings/notifications", settings_notifications_put, methods=["PUT"])
api_router.add_api_route("/settings/control-tiers", settings_control_tiers_get, methods=["GET"])
api_router.add_api_route("/settings/control-tiers", settings_control_tiers_put, methods=["PUT"])
api_router.add_api_route("/settings/export", settings_export, methods=["POST"])
api_router.add_api_route("/settings/{section_name}", settings_update_section, methods=["PUT"])
api_router.add_api_route("/settings/{section_name}/{key}", settings_update_key, methods=["PUT"])
api_router.add_api_route("/engine/schedule", engine_schedule, methods=["GET"])
api_router.add_api_route("/engine/run/{task_name}", engine_run_task, methods=["POST"])
api_router.add_api_route("/engine/status", engine_status, methods=["GET"])
api_router.add_api_route("/engine/start", engine_start, methods=["POST"])
api_router.add_api_route("/engine/stop", engine_stop, methods=["POST"])
api_router.add_api_route("/agents", agents_list, methods=["GET"])
api_router.add_api_route("/agents/{name}", agents_detail, methods=["GET"])
api_router.add_api_route("/agents/{name}/run", agents_run, methods=["POST"])
api_router.add_api_route("/agents/{name}/approve", agents_approve, methods=["PUT"])
api_router.add_api_route("/agents/{name}/stop", agents_stop, methods=["POST"])
api_router.add_api_route("/agents/{name}/start", agents_start, methods=["POST"])
api_router.add_api_route("/agents/{name}/context", agents_context, methods=["GET"])
api_router.add_api_route("/events", events_list, methods=["GET"])
api_router.add_api_route("/voice/transcribe", voice_transcribe, methods=["POST"])
api_router.add_api_route("/voice/synthesize", voice_synthesize, methods=["POST"])
api_router.add_api_route("/voice/status", voice_status, methods=["GET"])
api_router.add_api_route("/voice/pipeline", voice_pipeline, methods=["POST"])
api_router.add_api_route("/voice/cache/generate", voice_cache_generate, methods=["POST"])
api_router.add_api_route("/setup/start", setup_start, methods=["POST"])
api_router.add_api_route("/setup/step/{step_number}", setup_step, methods=["POST"])
api_router.add_api_route("/setup/skip/{step_number}", setup_skip, methods=["POST"])
api_router.add_api_route("/setup/progress", setup_progress, methods=["GET"])

app.include_router(api_router)
