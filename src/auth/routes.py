"""Auth API endpoints — Claude Desktop detection, legacy login, refresh, me."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    load_or_create_secret,
    verify_token,
)
from src.auth.models import create_user, get_user, verify_password
from src.security.ratelimit import RateLimiter, rate_limit

_limiter = RateLimiter()

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_USERS_PATH = _CONFIG_DIR / "users.toml"
_CLAUDE_CONFIG = Path.home() / "Library" / "Application Support" / "Claude" / "config.json"

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _get_secret() -> str:
    return load_or_create_secret(_CONFIG_DIR / "auth_secret.toml")


def _is_claude_desktop_running() -> bool:
    """Check if Claude Desktop process is alive."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Claude"],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_claude_desktop_authenticated() -> bool:
    """Check if Claude Desktop has a valid OAuth token cached."""
    if not _CLAUDE_CONFIG.exists():
        return False
    try:
        data = json.loads(_CLAUDE_CONFIG.read_text())
        token_cache = data.get("oauth:tokenCache", "")
        return bool(token_cache)
    except Exception:
        return False


def _get_claude_user_display() -> str:
    """Get a display name from personality.toml if available."""
    personality_path = _CONFIG_DIR / "personality.toml"
    if personality_path.exists():
        try:
            import toml as _toml
            data = _toml.load(personality_path)
            return data.get("user_display_name", "User")
        except Exception:
            pass
    return "User"


@router.get("/claude-desktop/status")
async def claude_desktop_status() -> dict[str, Any]:
    """Check Claude Desktop auth state without issuing tokens."""
    running = _is_claude_desktop_running()
    authenticated = _is_claude_desktop_authenticated() if running else False
    return {
        "running": running,
        "authenticated": authenticated,
    }


@router.post("/claude-desktop/login")
@rate_limit(_limiter, max_calls=5, window_seconds=60)
async def claude_desktop_login(request: Request) -> dict[str, str]:
    """Authenticate via Claude Desktop — if it's running and signed in, issue a session."""
    if not _is_claude_desktop_running():
        raise HTTPException(
            status_code=503,
            detail="Claude Desktop is not running. Please open Claude Desktop and sign in.",
        )
    if not _is_claude_desktop_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Claude Desktop is not signed in. Please sign in to Claude Desktop first.",
        )

    display_name = _get_claude_user_display()
    secret = _get_secret()
    return {
        "access_token": create_access_token(
            username=display_name, role="owner", secret=secret
        ),
        "refresh_token": create_refresh_token(
            username=display_name, secret=secret
        ),
    }


@router.post("/register")
async def register(body: RegisterRequest) -> dict[str, Any]:
    try:
        user = create_user(
            users_path=_USERS_PATH,
            username=body.username,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at,
    }


@router.post("/login")
@rate_limit(_limiter, max_calls=5, window_seconds=60)
async def login(request: Request, body: LoginRequest) -> dict[str, str]:
    user = get_user(users_path=_USERS_PATH, username=body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    secret = _get_secret()
    return {
        "access_token": create_access_token(
            username=user.username, role=user.role, secret=secret
        ),
        "refresh_token": create_refresh_token(
            username=user.username, secret=secret
        ),
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest) -> dict[str, str]:
    secret = _get_secret()
    payload = verify_token(body.refresh_token, secret=secret)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    username = payload["sub"]
    # For Claude Desktop sessions, user won't be in users.toml — just reissue
    return {
        "access_token": create_access_token(
            username=username, role="owner", secret=secret
        ),
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "username": user["sub"],
        "role": user["role"],
    }
