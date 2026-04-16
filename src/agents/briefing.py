"""BriefingAgent — wraps the briefing composer as an SDK agent."""

from __future__ import annotations

from src.briefing.composer import compose_briefing
from src.briefing.news_sources import get_rss_urls_for_enabled
from src.sdk.base import AgentConfig, BaseAgent, trigger
from src.settings.manager import load_briefing, load_news_sources


class BriefingAgent(BaseAgent):
    """Composes the daily morning briefing."""

    config = AgentConfig(
        name="briefing",
        description="Composes the daily morning briefing",
        permissions=[
            "read_calendar",
            "read_reminders",
            "web_requests",
            "send_notifications",
        ],
        schedule=None,  # Dynamically set from briefing_time config
    )

    @trigger("scheduled")
    async def compose(self) -> dict:
        """Run the full briefing pipeline."""
        await self.emit("briefing_composing", {
            "briefing_time": load_briefing().get("time", "07:30"),
        })

        news_cfg = load_news_sources()
        enabled = news_cfg.get("enabled", ["hackernews"])
        rss_urls, hn_enabled = get_rss_urls_for_enabled(enabled)

        result = await compose_briefing({
            "rss_urls": rss_urls,
            "hn_enabled": hn_enabled,
            "hn_limit": news_cfg.get("hn_limit", 5),
            "hn_min_score": news_cfg.get("hn_min_score", 100),
        })

        summary = {
            "section_count": len(result.sections),
            "generated_at": result.generated_at,
            "summary": result.summary,
        }

        await self.context.set("last_result", summary)
        await self.emit("briefing_ready", {
            "section_count": len(result.sections),
        })

        return summary

    @trigger("user_invoked")
    async def run_now(self, params: dict) -> dict:
        """User-triggered immediate briefing."""
        return await self.compose()
