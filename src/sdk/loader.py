"""Agent discovery — scans directories for BaseAgent subclasses."""

from __future__ import annotations

import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from src.sdk.base import BaseAgent

logger = logging.getLogger(__name__)


def discover_agents(directories: list[Path]) -> list[BaseAgent]:
    """Scan directories for .py files containing BaseAgent subclasses.

    Each valid agent class is instantiated and returned. Files that fail
    to import or contain no agents are silently skipped (logged as warnings).
    """
    agents: list[BaseAgent] = []

    for directory in directories:
        if not directory.is_dir():
            continue

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            try:
                found = _load_agents_from_file(py_file)
                agents.extend(found)
            except Exception:
                logger.warning("Failed to load agents from %s", py_file, exc_info=True)

    return agents


def _load_agents_from_file(path: Path) -> list[BaseAgent]:
    """Import a single .py file and return instances of any BaseAgent subclasses."""
    module_name = f"_jarvis_agent_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise

    agents: list[BaseAgent] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BaseAgent)
            and obj is not BaseAgent
            and hasattr(obj, "config")
        ):
            agents.append(obj())

    return agents
