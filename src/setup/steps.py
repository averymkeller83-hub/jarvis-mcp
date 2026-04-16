"""Setup step definitions and state management for the first-run flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SetupStep:
    """A single step in the first-run setup flow."""

    number: int
    name: str
    description: str
    required: bool
    completed: bool = False
    skipped: bool = False
    result: dict | None = None


@dataclass
class SetupState:
    """Tracks overall progress through the setup flow."""

    steps: list[SetupStep]
    current_step: int = 1
    started_at: str = ""
    completed_at: str | None = None


def create_setup_steps() -> list[SetupStep]:
    """Return all 12 setup steps with correct metadata."""
    definitions = [
        (1, "welcome", "Welcome to JARVIS", True),
        (2, "personalization", "What should I call you?", False),
        (3, "claude_connection", "Detect Claude Desktop and subscription tier", True),
        (4, "contacts", "macOS Contacts access and nickname map", False),
        (5, "services", "Choose service ecosystems", False),
        (6, "scout_sources", "Select Scout discovery sources", False),
        (7, "github_auth", "GitHub CLI or PAT authentication", False),
        (8, "colima_check", "Check Docker/Colima availability", False),
        (9, "briefing_prefs", "Briefing time and Obsidian vault", False),
        (10, "voice_setup", "Test microphone and TTS", False),
        (11, "first_scan", "Run initial Scout discovery", False),
        (12, "done", "Setup complete", False),
    ]
    return [
        SetupStep(number=n, name=name, description=desc, required=req)
        for n, name, desc, req in definitions
    ]


def get_step(state: SetupState, number: int) -> SetupStep | None:
    """Return the step with the given number, or None."""
    for step in state.steps:
        if step.number == number:
            return step
    return None


def advance(state: SetupState) -> SetupState:
    """Move to the next step in the flow."""
    if state.current_step < len(state.steps):
        state.current_step += 1
    return state


def skip_step(state: SetupState, number: int) -> SetupState:
    """Mark a step as skipped. Raises ValueError for required steps."""
    step = get_step(state, number)
    if step is None:
        raise ValueError(f"Step {number} does not exist")
    if step.required:
        raise ValueError(f"Step {number} ({step.name}) is required and cannot be skipped")
    step.skipped = True
    return state


def complete_step(
    state: SetupState, number: int, result: dict | None = None
) -> SetupState:
    """Mark a step as completed with optional result data."""
    step = get_step(state, number)
    if step is None:
        raise ValueError(f"Step {number} does not exist")
    step.completed = True
    step.result = result
    return state
