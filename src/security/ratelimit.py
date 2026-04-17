"""In-memory rate limiter for FastAPI — no external dependencies.

Usage:
    from src.security.ratelimit import RateLimiter, rate_limit

    limiter = RateLimiter()

    @app.post("/setup/verify")
    @rate_limit(limiter, max_calls=10, window_seconds=60)
    async def setup_verify(...):
        ...
"""

from __future__ import annotations

import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self) -> None:
        # {key: [timestamp, timestamp, ...]}
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_calls: int, window_seconds: int) -> bool:
        """Check if a request is allowed and record it if so."""
        now = time.monotonic()
        cutoff = now - window_seconds

        # Prune expired entries
        hits = self._hits[key]
        self._hits[key] = [t for t in hits if t > cutoff]
        hits = self._hits[key]

        if len(hits) >= max_calls:
            return False

        hits.append(now)
        return True

    def remaining(self, key: str, max_calls: int, window_seconds: int) -> int:
        """How many calls remain in the current window."""
        now = time.monotonic()
        cutoff = now - window_seconds
        hits = [t for t in self._hits[key] if t > cutoff]
        return max(0, max_calls - len(hits))

    def reset_after(self, key: str, window_seconds: int) -> float:
        """Seconds until the oldest entry in the window expires."""
        if not self._hits[key]:
            return 0.0
        now = time.monotonic()
        cutoff = now - window_seconds
        active = [t for t in self._hits[key] if t > cutoff]
        if not active:
            return 0.0
        return max(0.0, active[0] - cutoff)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    limiter: RateLimiter,
    max_calls: int = 10,
    window_seconds: int = 60,
) -> Callable:
    """Decorator that rate-limits a FastAPI endpoint by client IP."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Request object in args/kwargs
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                return await func(*args, **kwargs)

            key = f"{func.__name__}:{_get_client_ip(request)}"

            if not limiter.is_allowed(key, max_calls, window_seconds):
                remaining = limiter.remaining(key, max_calls, window_seconds)
                reset = limiter.reset_after(key, window_seconds)
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Try again in {int(reset) + 1} seconds.",
                    headers={
                        "Retry-After": str(int(reset) + 1),
                        "X-RateLimit-Limit": str(max_calls),
                        "X-RateLimit-Remaining": str(remaining),
                    },
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
