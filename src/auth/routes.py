"""Auth API endpoints — register, login, refresh, me."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    load_or_create_secret,
    verify_token,
)
from src.auth.models import create_user, get_user, verify_password

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_USERS_PATH = _CONFIG_DIR / "users.toml"

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
async def login(body: LoginRequest) -> dict[str, str]:
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
    user = get_user(users_path=_USERS_PATH, username=username)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "access_token": create_access_token(
            username=user.username, role=user.role, secret=secret
        ),
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "username": user["sub"],
        "role": user["role"],
    }
