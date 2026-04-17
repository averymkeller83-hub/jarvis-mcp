"""Shared types for messaging channel backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SendResult:
    """Outcome of sending a message through any channel."""

    success: bool
    message: str
    channel: str


@dataclass
class IncomingMessage:
    """A message received from any channel."""

    text: str
    sender: str
    channel: str
    timestamp: datetime
    raw: dict = field(default_factory=dict)
