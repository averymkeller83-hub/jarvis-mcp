"""Jarvis MCP Core Daemon — FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.brain.router import classify, control_intent, local_intent
from src.briefing.composer import compose_briefing
from src.briefing.writer import write_to_obsidian
from src.hands.executor import execute_control
from src.scout.cards import card_to_dict
from src.scout.engine import install_candidate, run_discovery
from src.scout.signals import Signal, log_signal
from src.scout.sources import load_sources

VERSION = "0.1.0"

_start_time: float = 0.0


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
            "settings": "placeholder",
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
    return {
        "personality": {
            "assistant_name": "JARVIS",
            "user_display_name": "Sir",
        },
        "voice": {
            "profile": "default",
            "wake_word_enabled": False,
            "hotkey": "alt+space",
        },
        "behavior": {
            "use_claude_for_chat": False,
            "do_not_disturb": False,
        },
    }
