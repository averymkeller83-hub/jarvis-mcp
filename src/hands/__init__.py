"""Hands — CONTROL surface handlers for Jarvis MCP."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ControlResult:
    """Outcome of a CONTROL action."""

    success: bool
    message: str
    action: str
    confirmed: bool
