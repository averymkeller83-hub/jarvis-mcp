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
