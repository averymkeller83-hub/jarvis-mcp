"""Verify channel credentials against live APIs."""

from __future__ import annotations

import re
import smtplib
from typing import Any

import httpx


async def verify_telegram(bot_token: str, chat_id: str) -> dict[str, Any]:
    """Verify Telegram bot token and chat ID are valid."""
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}
    if not chat_id:
        return {"ok": False, "error": "Chat ID is required"}

    async with httpx.AsyncClient(timeout=10) as client:
        # Verify bot token via getMe
        try:
            resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            data = resp.json()
            if not data.get("ok"):
                return {"ok": False, "error": "Invalid bot token"}
            bot_name = data["result"].get("username", "unknown")
        except Exception as exc:
            return {"ok": False, "error": f"Could not reach Telegram API: {exc}"}

        # Verify chat ID
        try:
            resp = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getChat",
                params={"chat_id": chat_id},
            )
            data = resp.json()
            if not data.get("ok"):
                return {
                    "ok": False,
                    "error": f"Bot @{bot_name} is valid, but chat ID '{chat_id}' is not accessible. "
                    "Make sure you've messaged the bot first.",
                    "bot_valid": True,
                    "bot_name": bot_name,
                }
        except Exception:
            return {"ok": False, "error": "Bot token is valid but could not verify chat ID"}

    return {"ok": True, "bot_name": bot_name, "chat_id": chat_id}


async def verify_discord(bot_token: str, channel_id: str) -> dict[str, Any]:
    """Verify Discord bot token and channel access."""
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}
    if not channel_id:
        return {"ok": False, "error": "Channel ID is required"}

    headers = {"Authorization": f"Bot {bot_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        # Verify bot token
        try:
            resp = await client.get("https://discord.com/api/v10/users/@me", headers=headers)
            if resp.status_code == 401:
                return {"ok": False, "error": "Invalid bot token"}
            if resp.status_code != 200:
                return {"ok": False, "error": f"Discord API error: {resp.status_code}"}
            bot_data = resp.json()
            bot_name = bot_data.get("username", "unknown")
        except Exception as exc:
            return {"ok": False, "error": f"Could not reach Discord API: {exc}"}

        # Verify channel access
        try:
            resp = await client.get(
                f"https://discord.com/api/v10/channels/{channel_id}", headers=headers
            )
            if resp.status_code == 404:
                return {
                    "ok": False,
                    "error": f"Bot {bot_name} is valid, but channel '{channel_id}' not found.",
                    "bot_valid": True,
                    "bot_name": bot_name,
                }
            if resp.status_code == 403:
                return {
                    "ok": False,
                    "error": f"Bot {bot_name} doesn't have access to channel '{channel_id}'.",
                    "bot_valid": True,
                    "bot_name": bot_name,
                }
            if resp.status_code != 200:
                return {"ok": False, "error": f"Channel check failed: {resp.status_code}"}
            channel_name = resp.json().get("name", channel_id)
        except Exception:
            return {"ok": False, "error": "Bot token valid but could not verify channel"}

    return {"ok": True, "bot_name": bot_name, "channel_name": channel_name}


async def verify_slack(bot_token: str, channel_id: str) -> dict[str, Any]:
    """Verify Slack bot token and channel access."""
    if not bot_token:
        return {"ok": False, "error": "Bot token is required"}
    if not channel_id:
        return {"ok": False, "error": "Channel ID is required"}

    headers = {"Authorization": f"Bearer {bot_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        # Verify bot token via auth.test
        try:
            resp = await client.post("https://slack.com/api/auth.test", headers=headers)
            data = resp.json()
            if not data.get("ok"):
                return {"ok": False, "error": f"Invalid bot token: {data.get('error', 'unknown')}"}
            team_name = data.get("team", "unknown")
            bot_name = data.get("user", "unknown")
        except Exception as exc:
            return {"ok": False, "error": f"Could not reach Slack API: {exc}"}

        # Verify channel access
        try:
            resp = await client.get(
                "https://slack.com/api/conversations.info",
                headers=headers,
                params={"channel": channel_id},
            )
            data = resp.json()
            if not data.get("ok"):
                return {
                    "ok": False,
                    "error": f"Bot is valid ({team_name}), but channel '{channel_id}' "
                    f"is not accessible: {data.get('error', 'unknown')}",
                    "bot_valid": True,
                    "bot_name": bot_name,
                    "team": team_name,
                }
            channel_name = data.get("channel", {}).get("name", channel_id)
        except Exception:
            return {"ok": False, "error": "Bot token valid but could not verify channel"}

    return {"ok": True, "bot_name": bot_name, "team": team_name, "channel_name": channel_name}


async def verify_email(
    smtp_host: str, smtp_port: str, username: str, password: str
) -> dict[str, Any]:
    """Verify SMTP credentials by connecting and authenticating."""
    if not smtp_host:
        return {"ok": False, "error": "SMTP host is required"}
    if not username or not password:
        return {"ok": False, "error": "Username and password are required"}

    port = int(smtp_port) if smtp_port else 587
    try:
        server = smtplib.SMTP(smtp_host, port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(username, password)
        server.quit()
    except smtplib.SMTPAuthenticationError:
        return {"ok": False, "error": "Authentication failed — check username and password"}
    except smtplib.SMTPConnectError:
        return {"ok": False, "error": f"Could not connect to {smtp_host}:{port}"}
    except Exception as exc:
        return {"ok": False, "error": f"SMTP error: {exc}"}

    return {"ok": True, "smtp_host": smtp_host, "username": username}


def verify_phone_format(target: str) -> dict[str, Any]:
    """Validate iMessage target format (phone number or email)."""
    if not target:
        return {"ok": False, "error": "Phone number or email is required"}

    target = target.strip()

    # Email format
    if "@" in target:
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", target):
            return {"ok": True, "target": target, "type": "email"}
        return {"ok": False, "error": "Invalid email format"}

    # Phone: strip formatting, check digits
    digits = re.sub(r"[\s\-\(\)\+]", "", target)
    if digits.isdigit() and 7 <= len(digits) <= 15:
        return {"ok": True, "target": target, "type": "phone"}

    return {"ok": False, "error": "Invalid phone number format"}
