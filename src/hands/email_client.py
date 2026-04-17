"""Email client — SMTP send and IMAP receive."""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from src.hands.types import IncomingMessage, SendResult

logger = logging.getLogger(__name__)


def _send_smtp(config: dict, message: str) -> SendResult:
    """Synchronous SMTP send (runs in thread)."""
    try:
        msg = MIMEText(message)
        msg["Subject"] = "JARVIS"
        msg["From"] = config["username"]
        msg["To"] = config["recipient"]

        with smtplib.SMTP(config["smtp_host"], int(config.get("smtp_port", 587))) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)

        return SendResult(
            success=True,
            message=f"Email sent to {config['recipient']}",
            channel="email",
        )
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return SendResult(
            success=False,
            message=f"Email send failed: {exc}",
            channel="email",
        )


async def send(config: dict, message: str) -> SendResult:
    """Send an email via SMTP (async wrapper)."""
    return await asyncio.to_thread(_send_smtp, config, message)


def _poll_imap(config: dict, since_uid: str = "1") -> list[IncomingMessage]:
    """Synchronous IMAP poll (runs in thread)."""
    messages: list[IncomingMessage] = []
    try:
        with imaplib.IMAP4_SSL(config["imap_host"]) as imap:
            imap.login(config["username"], config["password"])
            imap.select("INBOX")
            _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()

            for uid in uids:
                _, msg_data = imap.fetch(uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                sender = msg.get("From", "unknown")
                date_str = msg.get("Date", "")
                try:
                    ts = parsedate_to_datetime(date_str)
                except Exception:
                    ts = datetime.now(timezone.utc)

                messages.append(
                    IncomingMessage(
                        text=body.strip(),
                        sender=sender,
                        channel="email",
                        timestamp=ts,
                        raw={"uid": uid.decode(), "subject": msg.get("Subject", "")},
                    )
                )
    except Exception as exc:
        logger.warning("Email poll failed: %s", exc)

    return messages


async def poll(config: dict, since_uid: str = "1") -> list[IncomingMessage]:
    """Poll for unread emails via IMAP (async wrapper)."""
    return await asyncio.to_thread(_poll_imap, config, since_uid)


def _test_smtp(config: dict) -> bool:
    """Test SMTP connection."""
    try:
        with smtplib.SMTP(config["smtp_host"], int(config.get("smtp_port", 587))) as server:
            server.starttls()
            server.login(config["username"], config["password"])
        return True
    except Exception:
        return False


def _test_imap(config: dict) -> bool:
    """Test IMAP connection."""
    try:
        with imaplib.IMAP4_SSL(config["imap_host"]) as imap:
            imap.login(config["username"], config["password"])
        return True
    except Exception:
        return False


async def test_connection(config: dict) -> bool:
    """Test both SMTP and IMAP connections."""
    smtp_ok = await asyncio.to_thread(_test_smtp, config)
    if not smtp_ok:
        return False
    imap_ok = await asyncio.to_thread(_test_imap, config)
    return imap_ok
