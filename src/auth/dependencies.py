"""FastAPI dependencies for authentication."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

from src.auth.jwt import load_or_create_secret, verify_token

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _get_secret() -> str:
    return load_or_create_secret(_CONFIG_DIR / "auth_secret.toml")


async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header.

    Returns the decoded payload dict with 'sub' (username) and 'role'.
    Raises 401 if missing or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header[7:]
    secret = _get_secret()
    payload = verify_token(token, secret=secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return payload
