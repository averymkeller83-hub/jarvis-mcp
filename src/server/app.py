"""Jarvis MCP Core Daemon — FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.brain.router import classify, control_intent, local_intent

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


class ScoutInstallRequest(BaseModel):
    candidate_id: str


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
            "scout": "placeholder",
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


@app.get("/briefing")
async def briefing() -> dict[str, Any]:
    return {
        "sections": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/lessons")
async def lessons_list() -> dict[str, Any]:
    return {"lessons": [], "count": 0}


@app.post("/lessons/propose")
async def lessons_propose(body: LessonProposeRequest) -> dict[str, str]:
    return {
        "draft": f"Proposed lesson from correction: {body.correction}",
        "status": "pending_approval",
    }


@app.post("/scout/discover")
async def scout_discover() -> dict[str, Any]:
    return {
        "finds": [],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/scout/install")
async def scout_install(body: ScoutInstallRequest) -> dict[str, str]:
    return {"status": "not_implemented"}


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
