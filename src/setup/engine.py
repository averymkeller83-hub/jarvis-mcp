"""Setup orchestration — start, execute, skip, and track progress."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.setup.handlers import STEP_HANDLERS
from src.setup.steps import (
    SetupState,
    SetupStep,
    advance,
    complete_step,
    create_setup_steps,
    get_step,
    skip_step,
)

logger = logging.getLogger(__name__)

_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "setup_state.json"


def _save_state(state: SetupState) -> None:
    """Persist setup state to disk so it survives server restarts."""
    data = {
        "current_step": state.current_step,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "steps": [
            {
                "number": s.number,
                "name": s.name,
                "description": s.description,
                "required": s.required,
                "completed": s.completed,
                "skipped": s.skipped,
                "result": s.result,
            }
            for s in state.steps
        ],
    }
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(data, indent=2))


def _load_state() -> SetupState | None:
    """Load setup state from disk. Returns None if no saved state."""
    if not _STATE_PATH.exists():
        return None
    try:
        data = json.loads(_STATE_PATH.read_text())
        steps = [
            SetupStep(
                number=s["number"],
                name=s["name"],
                description=s["description"],
                required=s["required"],
                completed=s.get("completed", False),
                skipped=s.get("skipped", False),
                result=s.get("result"),
            )
            for s in data["steps"]
        ]
        return SetupState(
            steps=steps,
            current_step=data["current_step"],
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
        )
    except Exception:
        logger.warning("Could not load setup state from disk")
        return None


async def start_setup() -> SetupState:
    """Resume from saved state if available, otherwise create fresh."""
    saved = _load_state()
    if saved is not None:
        return saved
    steps = create_setup_steps()
    state = SetupState(
        steps=steps,
        current_step=1,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _save_state(state)
    return state


async def execute_step(
    state: SetupState, step_number: int, config: dict
) -> tuple[SetupState, dict]:
    """Run the handler for the given step number."""
    handler = STEP_HANDLERS.get(step_number)
    if handler is None:
        raise ValueError(f"No handler for step {step_number}")

    step = get_step(state, step_number)
    if step is None:
        raise ValueError(f"Step {step_number} does not exist")

    state, result = await handler(state, config)
    state = advance(state)
    _save_state(state)
    return state, result


async def skip_setup_step(
    state: SetupState, step_number: int
) -> tuple[SetupState, dict]:
    """Skip a step (validates that it's optional)."""
    state = skip_step(state, step_number)
    state = advance(state)
    _save_state(state)
    step = get_step(state, step_number)
    return state, {
        "skipped": True,
        "step": step_number,
        "name": step.name if step else "unknown",
    }


def is_setup_complete(state: SetupState) -> bool:
    """True when the final step has been completed."""
    if not state.steps:
        return False
    last = state.steps[-1]
    return last.completed


def get_setup_progress(state: SetupState) -> dict:
    """Return a summary of setup progress."""
    total = len(state.steps)
    completed = sum(1 for s in state.steps if s.completed)
    skipped = sum(1 for s in state.steps if s.skipped)
    remaining = total - completed - skipped
    percent = round((completed / total) * 100) if total else 0
    return {
        "total": total,
        "completed": completed,
        "skipped": skipped,
        "remaining": remaining,
        "percent": percent,
    }
