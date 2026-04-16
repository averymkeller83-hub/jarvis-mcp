"""ScoutAgent — wraps Scout discovery as an SDK agent."""

from __future__ import annotations

from src.scout.engine import run_discovery
from src.sdk.base import AgentConfig, BaseAgent, trigger


class ScoutAgent(BaseAgent):
    """Discovers tools, repos, and resources on a schedule."""

    config = AgentConfig(
        name="scout",
        description="Discovers tools, repos, and resources",
        permissions=["web_requests", "send_notifications"],
        schedule="0 */4 * * *",
    )

    @trigger("scheduled")
    async def scan(self) -> dict:
        """Run the full Scout discovery pipeline."""
        cards = await run_discovery()

        summary = {
            "finds_count": len(cards),
        }

        await self.context.set("latest_finds", [str(c) for c in cards])
        await self.context.set("last_result", summary)

        if cards:
            await self.emit("scout_new_finds", {
                "count": len(cards),
            })

        return summary

    @trigger("user_invoked")
    async def run_now(self, params: dict) -> dict:
        """User-triggered immediate discovery."""
        return await self.scan()
