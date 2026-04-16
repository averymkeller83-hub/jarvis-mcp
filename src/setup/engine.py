"""Setup orchestration — start, execute, skip, and track progress."""

from __future__ import annotations

from datetime import datetime, timezone

from src.setup.handlers import STEP_HANDLERS
from src.setup.steps import (
    SetupState,
    advance,
    complete_step,
    create_setup_steps,
    get_step,
    skip_step,
)


async def start_setup() -> SetupState:
    """Create a fresh setup state with all 12 steps."""
    steps = create_setup_steps()
    return SetupState(
        steps=steps,
        current_step=1,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


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
    return state, result


async def skip_setup_step(
    state: SetupState, step_number: int
) -> tuple[SetupState, dict]:
    """Skip a step (validates that it's optional)."""
    state = skip_step(state, step_number)
    state = advance(state)
    step = get_step(state, step_number)
    return state, {
        "skipped": True,
        "step": step_number,
        "name": step.name if step else "unknown",
    }


def is_setup_complete(state: SetupState) -> bool:
    """True when every required step has been completed."""
    for step in state.steps:
        if step.required and not step.completed:
            return False
    return True


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
