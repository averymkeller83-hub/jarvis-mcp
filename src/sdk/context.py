"""SharedContext — TOML-backed key-value store for agent data."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)


class SharedContext:
    """Agent shared key-value store, persisted to a TOML file.

    Keys are dot-namespaced (e.g. ``scout.latest_finds``).
    Writes are atomic via tmp-file + rename.
    """

    def __init__(self, store_path: Path) -> None:
        self._path = Path(store_path)
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            self._data = toml.load(self._path)
        else:
            self._data = {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            toml.dump(self._data, f)
        os.replace(tmp, self._path)

    async def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._flush()

    async def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._flush()
            return True
        return False

    async def list(self, prefix: str = "") -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]

    async def clear_namespace(self, namespace: str) -> int:
        prefix = f"{namespace}."
        keys = [k for k in self._data if k.startswith(prefix)]
        for k in keys:
            del self._data[k]
        if keys:
            self._flush()
        return len(keys)


class ScopedContext:
    """Namespace-restricted wrapper around SharedContext.

    Reads can access any key. Writes are restricted to the agent's
    own namespace — attempting to write outside it raises PermissionError.
    """

    def __init__(self, context: SharedContext, namespace: str) -> None:
        self._ctx = context
        self._ns = namespace

    async def get(self, key: str, default: Any = None) -> Any:
        return await self._ctx.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        if "." in key and not key.startswith(f"{self._ns}."):
            raise PermissionError(
                f"Agent '{self._ns}' cannot write to key '{key}'"
            )
        full_key = key if key.startswith(f"{self._ns}.") else f"{self._ns}.{key}"
        await self._ctx.set(full_key, value)

    async def delete(self, key: str) -> bool:
        full_key = key if key.startswith(f"{self._ns}.") else f"{self._ns}.{key}"
        return await self._ctx.delete(full_key)

    async def list(self, prefix: str = "") -> list[str]:
        return await self._ctx.list(prefix)

    async def clear_namespace(self, namespace: str) -> int:
        return await self._ctx.clear_namespace(namespace)
