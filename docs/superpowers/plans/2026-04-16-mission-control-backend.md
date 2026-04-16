# Mission Control Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT authentication, migrate all endpoints under `/api/` prefix, add event history, and serve the React SPA from FastAPI.

**Architecture:** New `src/auth/` package handles user storage (TOML-backed), password hashing (bcrypt), and JWT tokens (PyJWT). All existing endpoints get duplicated under `/api/` via an `APIRouter`. EventBus gains an in-memory ring buffer for event history. FastAPI mounts `dashboard/dist/` as static files with SPA fallback.

**Tech Stack:** Python 3.12, FastAPI, PyJWT, bcrypt, pytest

---

## File Structure

| File | Responsibility |
|---|---|
| `src/auth/__init__.py` | Package init |
| `src/auth/models.py` | User model, TOML storage, password hashing |
| `src/auth/jwt.py` | Token creation and verification |
| `src/auth/dependencies.py` | FastAPI dependency `get_current_user()` |
| `src/auth/routes.py` | Auth endpoints (register, login, refresh, me) |
| `src/sdk/events.py` | Add event history ring buffer to existing EventBus |
| `src/server/app.py` | API prefix, auth wiring, static files, CORS, event history endpoint |
| `tests/test_auth.py` | Auth module tests |
| `tests/test_agents.py` | Append API prefix + event history tests |
| `pyproject.toml` | Add bcrypt, PyJWT dependencies |

---

### Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add bcrypt and PyJWT to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "pydantic",
    "pydantic-settings",
    "click",
    "toml",
    "sqlite-utils",
    "bcrypt",
    "PyJWT",
]
```

- [ ] **Step 2: Install the new dependencies**

Run: `pip install bcrypt PyJWT`
Expected: Successfully installed

- [ ] **Step 3: Verify imports work**

Run: `python3 -c "import bcrypt; import jwt; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add bcrypt and PyJWT dependencies for auth"
```

---

### Task 2: Auth Models (User Storage + Password Hashing)

**Files:**
- Create: `src/auth/__init__.py`
- Create: `src/auth/models.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests for user models**

Create `tests/test_auth.py`:

```python
"""Tests for authentication module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.auth.models import (
    User,
    create_user,
    get_user,
    list_users,
    verify_password,
)


# ── User Models ────────────────────────────────────────────────────


def test_create_user(tmp_path: Path):
    user = create_user(
        users_path=tmp_path / "users.toml",
        username="avery",
        password="testpass123",
    )
    assert user.username == "avery"
    assert user.role == "admin"  # first user is admin
    assert user.password_hash != "testpass123"


def test_create_second_user_is_regular(tmp_path: Path):
    path = tmp_path / "users.toml"
    create_user(users_path=path, username="avery", password="pass1")
    user2 = create_user(users_path=path, username="bob", password="pass2")
    assert user2.role == "user"


def test_create_duplicate_user_raises(tmp_path: Path):
    path = tmp_path / "users.toml"
    create_user(users_path=path, username="avery", password="pass1")
    with pytest.raises(ValueError, match="already exists"):
        create_user(users_path=path, username="avery", password="pass2")


def test_get_user(tmp_path: Path):
    path = tmp_path / "users.toml"
    create_user(users_path=path, username="avery", password="pass1")
    user = get_user(users_path=path, username="avery")
    assert user is not None
    assert user.username == "avery"


def test_get_user_not_found(tmp_path: Path):
    path = tmp_path / "users.toml"
    assert get_user(users_path=path, username="nobody") is None


def test_verify_password(tmp_path: Path):
    path = tmp_path / "users.toml"
    create_user(users_path=path, username="avery", password="correct")
    user = get_user(users_path=path, username="avery")
    assert verify_password("correct", user.password_hash) is True
    assert verify_password("wrong", user.password_hash) is False


def test_list_users(tmp_path: Path):
    path = tmp_path / "users.toml"
    create_user(users_path=path, username="a", password="p1")
    create_user(users_path=path, username="b", password="p2")
    users = list_users(users_path=path)
    assert len(users) == 2
    names = {u.username for u in users}
    assert names == {"a", "b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py::test_create_user -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.auth'`

- [ ] **Step 3: Implement auth models**

Create `src/auth/__init__.py`:

```python
"""Jarvis authentication module."""
```

Create `src/auth/models.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/auth/__init__.py src/auth/models.py tests/test_auth.py
git commit -m "feat(auth): add User model with TOML storage and bcrypt hashing"
```

---

### Task 3: JWT Module (Token Creation + Verification)

**Files:**
- Create: `src/auth/jwt.py`
- Test: `tests/test_auth.py` (append)

- [ ] **Step 1: Write the failing tests for JWT**

Append to `tests/test_auth.py`:

```python
import time

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    load_or_create_secret,
)


# ── JWT ────────────────────────────────────────────────────────────


def test_load_or_create_secret(tmp_path: Path):
    path = tmp_path / "auth_secret.toml"
    secret1 = load_or_create_secret(path)
    assert len(secret1) >= 32
    secret2 = load_or_create_secret(path)
    assert secret1 == secret2  # stable across loads


def test_create_and_verify_access_token(tmp_path: Path):
    secret = load_or_create_secret(tmp_path / "auth_secret.toml")
    token = create_access_token(
        username="avery", role="admin", secret=secret
    )
    payload = verify_token(token, secret=secret)
    assert payload["sub"] == "avery"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token(tmp_path: Path):
    secret = load_or_create_secret(tmp_path / "auth_secret.toml")
    token = create_refresh_token(username="avery", secret=secret)
    payload = verify_token(token, secret=secret)
    assert payload["sub"] == "avery"
    assert payload["type"] == "refresh"


def test_verify_expired_token(tmp_path: Path):
    secret = load_or_create_secret(tmp_path / "auth_secret.toml")
    token = create_access_token(
        username="avery", role="admin", secret=secret, ttl_seconds=0
    )
    time.sleep(1)
    assert verify_token(token, secret=secret) is None


def test_verify_invalid_token(tmp_path: Path):
    secret = load_or_create_secret(tmp_path / "auth_secret.toml")
    assert verify_token("garbage.token.here", secret=secret) is None


def test_verify_wrong_secret(tmp_path: Path):
    secret = load_or_create_secret(tmp_path / "auth_secret.toml")
    token = create_access_token(
        username="avery", role="admin", secret=secret
    )
    assert verify_token(token, secret="wrong-secret") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py::test_load_or_create_secret -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.auth.jwt'`

- [ ] **Step 3: Implement JWT module**

Create `src/auth/jwt.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 13 passed (7 models + 6 JWT)

- [ ] **Step 5: Commit**

```bash
git add src/auth/jwt.py tests/test_auth.py
git commit -m "feat(auth): add JWT token creation and verification"
```

---

### Task 4: Auth Endpoints (Register, Login, Refresh, Me)

**Files:**
- Create: `src/auth/dependencies.py`
- Create: `src/auth/routes.py`
- Test: `tests/test_auth.py` (append)

- [ ] **Step 1: Write the failing tests for auth endpoints**

Append to `tests/test_auth.py`:

```python
import httpx
from httpx import ASGITransport

from src.server.app import app


# ── Auth API ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:7900")


@pytest.mark.asyncio
async def test_register(client: httpx.AsyncClient):
    resp = await client.post("/api/auth/register", json={
        "username": "testuser",
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["role"] == "admin"  # first user


@pytest.mark.asyncio
async def test_register_duplicate(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "dupuser",
        "password": "pass1",
    })
    resp = await client.post("/api/auth/register", json={
        "username": "dupuser",
        "password": "pass2",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "loginuser",
        "password": "mypass",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "loginuser",
        "password": "mypass",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "wrongpw",
        "password": "correct",
    })
    resp = await client.post("/api/auth/login", json={
        "username": "wrongpw",
        "password": "incorrect",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: httpx.AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "username": "ghost",
        "password": "nope",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "refreshuser",
        "password": "pass",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "refreshuser",
        "password": "pass",
    })
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(client: httpx.AsyncClient):
    resp = await client.post("/api/auth/refresh", json={
        "refresh_token": "garbage",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: httpx.AsyncClient):
    await client.post("/api/auth/register", json={
        "username": "meuser",
        "password": "pass",
    })
    login_resp = await client.post("/api/auth/login", json={
        "username": "meuser",
        "password": "pass",
    })
    token = login_resp.json()["access_token"]
    resp = await client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    assert resp.json()["username"] == "meuser"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: httpx.AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py::test_register -v`
Expected: FAIL — 404 (endpoint doesn't exist)

- [ ] **Step 3: Implement auth dependencies**

Create `src/auth/dependencies.py`:

```python
"""FastAPI dependencies for authentication."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, HTTPException, Request

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
```

- [ ] **Step 4: Implement auth routes**

Create `src/auth/routes.py`:

```python
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
```

- [ ] **Step 5: Wire auth routes into app.py**

In `src/server/app.py`, add after the existing imports:

```python
from src.auth.routes import router as auth_router
```

Add after `app.add_middleware(...)`:

```python
app.include_router(auth_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 22 passed (7 models + 6 JWT + 9 API)

- [ ] **Step 7: Commit**

```bash
git add src/auth/dependencies.py src/auth/routes.py src/server/app.py tests/test_auth.py
git commit -m "feat(auth): add register/login/refresh/me endpoints with JWT"
```

---

### Task 5: API Prefix Migration

**Files:**
- Modify: `src/server/app.py`
- Test: `tests/test_auth.py` (append)

- [ ] **Step 1: Write the failing tests for API prefix**

Append to `tests/test_auth.py`:

```python
# ── API Prefix ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_prefix_status(client: httpx.AsyncClient):
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["daemon"] == "running"


@pytest.mark.asyncio
async def test_api_prefix_health(client: httpx.AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_api_prefix_agents(client: httpx.AsyncClient):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    assert "agents" in resp.json()


@pytest.mark.asyncio
async def test_legacy_routes_still_work(client: httpx.AsyncClient):
    resp = await client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["daemon"] == "running"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py::test_api_prefix_status -v`
Expected: FAIL — 404 (no `/api/status` route yet)

- [ ] **Step 3: Add API prefix router to app.py**

In `src/server/app.py`, add this import at the top:

```python
from fastapi import APIRouter
```

After the `app.include_router(auth_router)` line, add:

```python
# Create /api prefix router that mirrors all existing endpoints
api_router = APIRouter(prefix="/api")
```

Then for each existing endpoint handler, add a duplicate route on `api_router`. The simplest approach: after all the existing `@app` endpoint definitions (but before the voice/setup sections or at the very end), add:

```python
# ── API-prefixed routes (mirrors of legacy routes) ─────────────────

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 26 passed

- [ ] **Step 5: Run existing tests to check no regressions**

Run: `python3 -m pytest tests/test_sdk.py tests/test_agents.py -q`
Expected: All pass (56 previously)

- [ ] **Step 6: Commit**

```bash
git add src/server/app.py tests/test_auth.py
git commit -m "feat(api): add /api/ prefix routes mirroring all existing endpoints"
```

---

### Task 6: Event History Ring Buffer

**Files:**
- Modify: `src/sdk/events.py`
- Modify: `src/server/app.py` (add event history endpoint)
- Test: `tests/test_auth.py` (append)

- [ ] **Step 1: Write the failing tests for event history**

Append to `tests/test_auth.py`:

```python
from src.sdk.events import EventBus


# ── Event History ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_history_records_events():
    bus = EventBus(history_size=10)
    await bus.emit("test_event", {"key": "val"}, source="test")
    history = bus.get_history()
    assert len(history) == 1
    assert history[0]["event"] == "test_event"
    assert history[0]["data"]["key"] == "val"
    assert history[0]["source"] == "test"


@pytest.mark.asyncio
async def test_event_history_respects_size_limit():
    bus = EventBus(history_size=3)
    for i in range(5):
        await bus.emit("evt", {"i": i}, source="test")
    history = bus.get_history()
    assert len(history) == 3
    assert history[0]["data"]["i"] == 2  # oldest kept
    assert history[2]["data"]["i"] == 4  # newest


@pytest.mark.asyncio
async def test_event_history_filter_by_source():
    bus = EventBus(history_size=10)
    await bus.emit("a", {}, source="agent1")
    await bus.emit("b", {}, source="agent2")
    await bus.emit("c", {}, source="agent1")
    history = bus.get_history(source="agent1")
    assert len(history) == 2
    assert all(h["source"] == "agent1" for h in history)


@pytest.mark.asyncio
async def test_event_history_default_empty():
    bus = EventBus()
    assert bus.get_history() == []


@pytest.mark.asyncio
async def test_api_events_history(client: httpx.AsyncClient):
    resp = await client.get("/api/events/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert isinstance(data["events"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py::test_event_history_records_events -v`
Expected: FAIL — `TypeError: EventBus.__init__() got an unexpected keyword argument 'history_size'`

- [ ] **Step 3: Add history ring buffer to EventBus**

Modify `src/sdk/events.py`. Replace the `__init__` method and add `get_history`:

```python
class EventBus:
    """Lightweight async event bus.

    Subscribers are async callables that receive a single dict argument.
    Failed subscribers are logged but do not block the emitter or other
    subscribers.
    """

    def __init__(self, history_size: int = 200) -> None:
        self._subs: dict[str, list[Callable]] = {}
        self._history: list[dict[str, Any]] = []
        self._history_size = history_size
```

In the `emit` method, after building the `payload` dict and before calling subscribers, add history recording:

```python
    async def emit(self, event_name: str, data: dict, source: str) -> None:
        payload: dict[str, Any] = {
            **data,
            "_source": source,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Record to history ring buffer
        self._history.append({
            "event": event_name,
            "data": data,
            "source": source,
            "timestamp": payload["_timestamp"],
        })
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        listeners = self._subs.get(event_name, [])
        if not listeners:
            return

        results = await asyncio.gather(
            *(self._safe_call(cb, payload) for cb in listeners),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "EventBus subscriber for %r failed: %s", event_name, result
                )
```

Add the `get_history` method:

```python
    def get_history(
        self, source: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Return recorded events, optionally filtered by source."""
        events = self._history
        if source is not None:
            events = [e for e in events if e["source"] == source]
        if limit is not None:
            events = events[-limit:]
        return events
```

- [ ] **Step 4: Add event history API endpoint**

In `src/server/app.py`, add after the existing `/events` endpoint:

```python
@app.get("/events/history")
async def events_history(
    source: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if _agent_manager is None:
        return {"events": [], "count": 0}
    events = _agent_manager.event_bus.get_history(source=source, limit=limit)
    return {"events": events, "count": len(events)}
```

Also add this route to the `api_router` block:

```python
api_router.add_api_route("/events/history", events_history, methods=["GET"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: 31 passed

- [ ] **Step 6: Run SDK tests to check no regressions**

Run: `python3 -m pytest tests/test_sdk.py -q`
Expected: 44 passed (EventBus tests still work with new optional param)

- [ ] **Step 7: Commit**

```bash
git add src/sdk/events.py src/server/app.py tests/test_auth.py
git commit -m "feat(events): add event history ring buffer + /events/history endpoint"
```

---

### Task 7: Static File Serving + CORS Update

**Files:**
- Modify: `src/server/app.py`
- Modify: `.gitignore`

- [ ] **Step 1: Create a minimal dashboard placeholder**

```bash
mkdir -p dashboard/dist
```

Create `dashboard/dist/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Jarvis Mission Control</title></head>
<body><div id="root">Loading Mission Control...</div></body>
</html>
```

- [ ] **Step 2: Add static file serving to app.py**

In `src/server/app.py`, add to the imports:

```python
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
```

At the very end of the file (after all route definitions), add:

```python
# ── Static file serving (SPA) ──────────────────────────────────────

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"

if _DASHBOARD_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_DASHBOARD_DIR / "assets"), name="assets") if (_DASHBOARD_DIR / "assets").is_dir() else None

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        """Serve static files or fall back to index.html for SPA routing."""
        file_path = _DASHBOARD_DIR / path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_DASHBOARD_DIR / "index.html")
```

- [ ] **Step 3: Update CORS to allow Vite dev server**

In `src/server/app.py`, update the CORS middleware:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://127.0.0.1:*",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Add dashboard/dist to .gitignore**

Append to `.gitignore`:

```
# Dashboard build output (generated by npm run build)
dashboard/dist/
dashboard/node_modules/
```

- [ ] **Step 5: Verify the SPA fallback works**

Run: `python3 -m pytest tests/test_auth.py tests/test_agents.py tests/test_sdk.py -q`
Expected: All tests pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/server/app.py .gitignore dashboard/dist/index.html
git commit -m "feat(server): add static file serving for dashboard SPA + CORS for Vite"
```

---

### Task 8: Full Test Run + Final Verification

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/test_auth.py tests/test_sdk.py tests/test_agents.py -v`
Expected: All pass (~87 total: 31 auth + 44 SDK + 12 agents)

- [ ] **Step 2: Verify API prefix works end-to-end**

Run: `python3 -c "
import asyncio, httpx
from httpx import ASGITransport
from src.server.app import app

async def check():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://127.0.0.1:7900') as c:
        r1 = await c.get('/api/health')
        r2 = await c.get('/api/status')
        r3 = await c.get('/api/agents')
        r4 = await c.get('/api/events/history')
        print(f'health: {r1.status_code}, status: {r2.status_code}, agents: {r3.status_code}, events: {r4.status_code}')
asyncio.run(check())
"`
Expected: `health: 200, status: 200, agents: 200, events: 200`

- [ ] **Step 3: Commit (if any cleanup needed)**

```bash
git status
# Only commit if there are changes
```

---

## Self-Review

**Spec coverage check:**

| Spec Section | Covered By |
|---|---|
| 2. Auth — User model, bcrypt | Task 2 |
| 2. Auth — JWT tokens | Task 3 |
| 2. Auth — Endpoints (register/login/refresh/me) | Task 4 |
| 2. Auth — Protection dependency | Task 4 |
| 2. Auth — First user is admin | Task 2 |
| 5. API prefix migration | Task 5 |
| 5. Event history ring buffer | Task 6 |
| 5. Static file serving + SPA fallback | Task 7 |
| 5. CORS update | Task 7 |
| 6. Backend testing | Tasks 2-6 |

**Not covered (deferred to Plan 2: Frontend Dashboard):**
- Sections 1, 3, 4, 6 (frontend): project scaffold, pages, components, frontend testing
- Auth protection on all `/api/*` routes (will be wired when frontend is ready — currently only `/api/auth/me` is protected to avoid breaking existing Telegram/LaunchAgent integrations)

**Placeholder scan:** No TBDs or TODOs. Every step has code.

**Type consistency:** `User` dataclass fields match across Tasks 2 and 4. `create_access_token` / `create_refresh_token` / `verify_token` signatures match between Task 3 (definition) and Task 4 (usage). `EventBus.__init__` optional `history_size` param is backward-compatible with existing tests.
