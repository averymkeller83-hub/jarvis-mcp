"""Source configuration and loading for the Scout module."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import toml

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


@dataclass
class ScoutSource:
    """A single Scout data source."""

    name: str
    enabled: bool
    cadence: str  # "hourly" | "daily" | "on_demand"
    description: str
    urls: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)


def load_sources(config_path: str | None = None) -> list[ScoutSource]:
    """Load Scout sources from TOML config, falling back to the example file."""
    if config_path:
        path = Path(config_path)
    else:
        path = CONFIG_DIR / "scout_sources.toml"
        if not path.exists():
            path = CONFIG_DIR / "scout_sources.example.toml"

    if not path.exists():
        return []

    raw = toml.load(path)
    sources_section = raw.get("sources", {})
    results: list[ScoutSource] = []

    for name, cfg in sources_section.items():
        # Pull out known fields; everything else goes into config
        known_keys = {"enabled", "cadence", "description", "urls", "feeds"}
        extra: dict = {k: v for k, v in cfg.items() if k not in known_keys}

        # Merge feeds into urls for RSS-type sources
        urls = cfg.get("urls", []) or cfg.get("feeds", []) or []

        results.append(
            ScoutSource(
                name=name,
                enabled=cfg.get("enabled", False),
                cadence=cfg.get("cadence", "daily"),
                description=cfg.get("description", ""),
                urls=urls,
                config=extra,
            )
        )

    return results


def get_enabled_sources(config_path: str | None = None) -> list[ScoutSource]:
    """Return only enabled sources."""
    return [s for s in load_sources(config_path) if s.enabled]


def get_hourly_sources(config_path: str | None = None) -> list[ScoutSource]:
    """Return enabled sources with hourly cadence."""
    return [s for s in load_sources(config_path) if s.enabled and s.cadence == "hourly"]


def get_daily_sources(config_path: str | None = None) -> list[ScoutSource]:
    """Return enabled sources with daily cadence."""
    return [s for s in load_sources(config_path) if s.enabled and s.cadence == "daily"]
