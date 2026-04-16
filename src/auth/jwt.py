"""JWT token creation and verification."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
import toml

ACCESS_TTL = 900  # 15 minutes
REFRESH_TTL = 604800  # 7 days
ALGORITHM = "HS256"


def load_or_create_secret(secret_path: Path) -> str:
    """Load JWT secret from TOML file, or generate and save one."""
    if secret_path.exists():
        data = toml.load(secret_path)
        return data.get("secret", "")

    secret = secrets.token_hex(32)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = secret_path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        toml.dump({"secret": secret}, f)
    os.replace(tmp, secret_path)
    return secret


def create_access_token(
    username: str,
    role: str,
    secret: str,
    ttl_seconds: int = ACCESS_TTL,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(
    username: str,
    secret: str,
    ttl_seconds: int = REFRESH_TTL,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_token(token: str, secret: str) -> dict | None:
    """Decode and validate a JWT. Returns payload dict or None."""
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
