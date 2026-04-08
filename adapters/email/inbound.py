"""IMAP inbound polling — fetch unseen emails, parse, sanitize, write intents.

D-07: Poll IMAP inbox → parse → create intent.
D-09: Message-ID header as idempotency key.
D-10: DKIM/SPF verification is informational (log but don't reject).
ADAPT-04: sanitize_email() is the trust boundary — called before any DB write.
"""

from __future__ import annotations

import asyncio
import email
import email.message
import email.policy
import json
import logging
import uuid

import asyncpg
from aioimaplib import aioimaplib

from adapters.sanitize import SanitizationError, SanitizedIntent, sanitize_email

__all__ = ["poll_inbox", "process_message"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Body extraction helper
# ---------------------------------------------------------------------------


def _extract_body(msg: email.message.EmailMessage) -> str:
    """Extract text body from an EmailMessage.

    Prefers text/plain. Falls back to text/html (stripped). Final fallback: str(msg).
    """
    if msg.is_multipart():
        # Walk parts preferring plain text
        plain: str | None = None
        html: str | None = None
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and plain is None:
                try:
                    plain = part.get_content()
                except Exception:
                    plain = str(part.get_payload(decode=True) or "")
            elif ct == "text/html" and html is None:
                try:
                    html_raw = part.get_content()
                except Exception:
                    html_raw = str(part.get_payload(decode=True) or "")
                # Strip HTML tags minimally — remove < ... > blocks
                import re

                html = re.sub(r"<[^>]+>", "", html_raw)
        if plain is not None:
            return plain
        if html is not None:
            return html
        return str(msg)
    else:
        try:
            body_part = msg.get_body(preferencelist=("plain",))
            if body_part is not None:
                return body_part.get_content()
        except Exception:
            pass
        try:
            return str(msg.get_payload(decode=True) or "")
        except Exception:
            pass
        return str(msg)


# ---------------------------------------------------------------------------
# Core processing function
# ---------------------------------------------------------------------------


async def process_message(
    raw_bytes: bytes,
    actor_id: str,
    conn: asyncpg.Connection,
) -> str | None:
    """Parse, sanitize, dedup-check, and insert an email as an intent.

    Returns the new intent id (str) on success, None on skip or sanitization failure.

    ADAPT-04: sanitize_email() is called before any DB write (trust boundary).
    D-09: Message-ID is the idempotency key — duplicate silently skipped.
    """
    # 1. Parse raw bytes
    msg: email.message.EmailMessage = email.message_from_bytes(
        raw_bytes, policy=email.policy.default
    )

    # 2. Extract fields
    message_id: str = (msg.get("Message-ID") or "").strip()
    sender: str = msg.get("From") or ""
    subject: str = msg.get("Subject") or ""
    body: str = _extract_body(msg)

    # 3. Synthetic ID if missing
    if not message_id:
        message_id = f"<synthetic-{uuid.uuid4()}@eclusa.local>"
        logger.debug("Generated synthetic Message-ID: %s", message_id)

    # 4. ADAPT-04 trust boundary: sanitize before any DB write
    result = sanitize_email(message_id, sender, subject, body)
    if isinstance(result, SanitizationError):
        logger.warning(
            "Sanitization failed for Message-ID %r: %s", message_id, result.reason
        )
        return None
    sanitized: SanitizedIntent = result

    # 5. Dedup check — D-09
    existing = await conn.fetchval(
        "SELECT 1 FROM intent WHERE context->>'message_id' = $1 AND source = 'email'",
        message_id,
    )
    if existing:
        logger.debug("Duplicate Message-ID %r — skipping", message_id)
        return None

    # 6. Insert intent
    intent_id = await conn.fetchval(
        """
        INSERT INTO intent (id, source, raw, context, created_by)
        VALUES (gen_random_uuid(), 'email', $1, $2::jsonb, $3::uuid)
        RETURNING id::text
        """,
        sanitized.raw,
        json.dumps(
            {
                "message_id": message_id,
                "sender": sanitized.sender_email,
                "subject": sanitized.subject,
            }
        ),
        actor_id,
    )
    logger.info("Created intent %s from email Message-ID %r", intent_id, message_id)
    return intent_id


# ---------------------------------------------------------------------------
# IMAP fetch helper
# ---------------------------------------------------------------------------


async def _fetch_unseen(
    imap: aioimaplib.IMAP4_SSL,
) -> list[tuple[bytes, bytes]]:
    """Fetch UNSEEN messages from IMAP. Returns list of (uid, raw_bytes) pairs."""
    res, data = await imap.uid("search", None, "UNSEEN")
    if res != "OK" or not data[0]:
        return []
    results: list[tuple[bytes, bytes]] = []
    for uid in data[0].split():
        res, msg_data = await imap.uid("fetch", uid, "(RFC822)")
        if res == "OK" and len(msg_data) > 1 and msg_data[1]:
            results.append((uid, msg_data[1]))
    return results


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------


async def poll_inbox(
    host: str,
    user: str,
    password: str,
    actor_id: str,
    pool: asyncpg.Pool,
    interval: int = 30,
) -> None:
    """Background asyncio task — polls IMAP INBOX for UNSEEN messages.

    Fetches unseen messages, calls process_message for each (sanitize + dedup + insert),
    marks processed messages as SEEN, then sleeps for `interval` seconds.

    Uses asyncio.wait_for with timeout=15s per poll cycle to guard against IMAP hangs.
    IMAP4_SSL created with timeout=10 per connection (Pitfall 2).
    """
    imap = aioimaplib.IMAP4_SSL(host=host, timeout=10)
    await imap.wait_hello_from_server()
    await imap.login(user, password)
    await imap.select()

    logger.info(
        "IMAP poller started for %s@%s — polling every %ds", user, host, interval
    )

    while True:
        try:
            pairs = await asyncio.wait_for(_fetch_unseen(imap), timeout=15)
            for uid, raw_bytes in pairs:
                async with pool.acquire() as conn:
                    await process_message(raw_bytes, actor_id, conn)
                # Mark SEEN after processing regardless of outcome (no retry on sanitization failure)
                await imap.uid("store", uid, "+FLAGS", r"\Seen")
        except asyncio.TimeoutError:
            logger.warning("IMAP poll timed out — retrying after sleep")
        except Exception:
            logger.exception(
                "Unexpected error in IMAP poll cycle — continuing after sleep"
            )
        await asyncio.sleep(interval)
