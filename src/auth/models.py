"""User model and TOML-backed storage."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import toml


@dataclass
class User:
    username: str
    password_hash: str
    role: str  # "admin" or "user"
    created_at: str


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _load_users(users_path: Path) -> dict:
    if users_path.exists():
        return toml.load(users_path)
    return {}


def _save_users(users_path: Path, data: dict) -> None:
    users_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = users_path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        toml.dump(data, f)
    os.replace(tmp, users_path)


def create_user(
    users_path: Path, username: str, password: str
) -> User:
    data = _load_users(users_path)
    if username in data:
        raise ValueError(f"User '{username}' already exists")

    role = "admin" if len(data) == 0 else "user"
    now = datetime.now(timezone.utc).isoformat()
    password_hash = _hash_password(password)

    data[username] = {
        "password_hash": password_hash,
        "role": role,
        "created_at": now,
    }
    _save_users(users_path, data)

    return User(
        username=username,
        password_hash=password_hash,
        role=role,
        created_at=now,
    )


def get_user(users_path: Path, username: str) -> User | None:
    data = _load_users(users_path)
    entry = data.get(username)
    if entry is None:
        return None
    return User(
        username=username,
        password_hash=entry["password_hash"],
        role=entry["role"],
        created_at=entry.get("created_at", ""),
    )


def list_users(users_path: Path) -> list[User]:
    data = _load_users(users_path)
    return [
        User(
            username=name,
            password_hash=entry["password_hash"],
            role=entry["role"],
            created_at=entry.get("created_at", ""),
        )
        for name, entry in data.items()
    ]
