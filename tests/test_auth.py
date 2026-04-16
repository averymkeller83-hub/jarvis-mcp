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
