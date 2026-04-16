"""Reaction tracking — append-only signal log for Scout candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "memory"
DEFAULT_SIGNAL_LOG = MEMORY_DIR / "scout_signals.jsonl"


@dataclass
class Signal:
    """A user reaction to a Scout candidate."""

    candidate_id: str
    action: str  # "installed" | "dismissed" | "expanded" | "ignored"
    reason: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def log_signal(signal: Signal, log_path: str | None = None) -> None:
    """Append a signal to the JSONL log file."""
    path = Path(log_path) if log_path else DEFAULT_SIGNAL_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(asdict(signal)) + "\n")


def load_signals(log_path: str | None = None) -> list[Signal]:
    """Load all signals from the JSONL log file."""
    path = Path(log_path) if log_path else DEFAULT_SIGNAL_LOG
    if not path.exists():
        return []

    signals: list[Signal] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                signals.append(Signal(
                    candidate_id=data.get("candidate_id", ""),
                    action=data.get("action", "ignored"),
                    reason=data.get("reason"),
                    timestamp=data.get("timestamp", ""),
                ))
            except (json.JSONDecodeError, TypeError):
                continue  # skip malformed lines
    return signals


def get_source_weights(signals: list[Signal]) -> dict[str, float]:
    """Compute per-source weights from user signals.

    Installs boost a source's weight, dismissals penalize.
    Expanded and ignored are neutral-ish nudges.
    """
    weights: dict[str, float] = {}
    source_counts: dict[str, int] = {}

    # We track weight adjustments per candidate_id prefix (source name encoded in id)
    # In practice, we'd look up the candidate's source. For now we use candidate_id
    # as the grouping key.
    action_deltas = {
        "installed": 1.0,
        "expanded": 0.3,
        "ignored": -0.1,
        "dismissed": -0.5,
    }

    for sig in signals:
        cid = sig.candidate_id
        delta = action_deltas.get(sig.action, 0.0)
        weights[cid] = weights.get(cid, 0.0) + delta
        source_counts[cid] = source_counts.get(cid, 0) + 1

    return weights
