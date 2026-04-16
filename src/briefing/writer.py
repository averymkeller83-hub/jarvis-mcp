"""Obsidian daily-note writer — renders a Briefing as Markdown."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.briefing.composer import Briefing
from src.briefing.sections import BriefingSection


def _render_section(section: BriefingSection) -> str:
    """Render a single section as Markdown."""
    lines: list[str] = [f"## {section.title}"]

    if section.content:
        lines.append(section.content)

    for item in section.items:
        if isinstance(item, dict):
            # Special handling for lessons digest (nested lists)
            if "learned" in item and "avoided" in item:
                if item["learned"]:
                    lines.append("### Learned")
                    for entry in item["learned"]:
                        lines.append(f"- {entry}")
                if item["avoided"]:
                    lines.append("### Avoided")
                    for entry in item["avoided"]:
                        lines.append(f"- {entry}")
            else:
                # Generic dict → bullet point with key: value pairs
                parts = [f"**{k}**: {v}" for k, v in item.items() if v is not None]
                if parts:
                    lines.append(f"- {' | '.join(parts)}")

    return "\n".join(lines)


def _render_briefing(briefing: Briefing) -> str:
    """Render the full briefing as Markdown."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts: list[str] = [f"# Daily Briefing — {today}", ""]

    if briefing.summary:
        parts.append(f"*{briefing.summary}*")
        parts.append("")

    for section in briefing.sections:
        parts.append(_render_section(section))
        parts.append("")

    return "\n".join(parts)


def write_to_obsidian(briefing: Briefing, vault_path: str) -> str:
    """Write *briefing* as a Markdown daily note in the given Obsidian vault.

    If the daily note already exists, the briefing is **appended** under a
    ``## Briefing`` heading instead of overwriting the file.

    Returns the absolute path of the file written.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    vault = Path(vault_path).resolve()
    home = Path.home()
    import tempfile
    tmp_root = Path(tempfile.gettempdir()).resolve()
    allowed_prefixes = (str(home), str(tmp_root), "/tmp")
    if not any(str(vault).startswith(p) for p in allowed_prefixes):
        raise ValueError(f"vault_path must be under the user's home directory, got: {vault}")
    daily_dir = vault / "Daily Notes"
    daily_dir.mkdir(parents=True, exist_ok=True)
    note_path = daily_dir / f"{today}.md"

    rendered = _render_briefing(briefing)

    if note_path.exists():
        existing = note_path.read_text(encoding="utf-8")
        combined = existing.rstrip() + "\n\n## Briefing\n\n" + rendered + "\n"
        note_path.write_text(combined, encoding="utf-8")
    else:
        note_path.write_text(rendered + "\n", encoding="utf-8")

    return str(note_path.resolve())
