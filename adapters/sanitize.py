"""Trust boundary sanitization — raw adapter input → SanitizedIntent | SanitizationError.

D-15: All inbound adapter messages are raw untrusted text.
D-16: Structured sanitization: strip control chars, validate length limits.
D-17: Sanitized intent is a Pydantic model validated before DB insertion.

OWASP LLM01:2025 — email is an indirect prompt injection surface.
Raw email content must never reach judgment passes without passing through here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, field_validator

__all__ = [
    "CONTROL_CHAR_RE",
    "MAX_RAW_LENGTH",
    "SanitizedIntent",
    "SanitizationError",
    "sanitize_email",
]

# Control characters (ASCII 0-8, 11-12, 14-31, 127) — strip from all inbound text
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Maximum raw content length in characters
MAX_RAW_LENGTH = 8_000


class SanitizedIntent(BaseModel):
    """Validated, sanitized representation of an inbound adapter message."""

    source_message_id: str  # Message-ID header (idempotency key, D-09)
    raw: str  # stripped, length-capped original text
    sender_email: str  # from address — must be non-empty (min_length=1)
    subject: str  # email subject, stripped of control chars

    @field_validator("raw", mode="before")
    @classmethod
    def strip_and_cap(cls, v: str) -> str:
        """Strip control characters and cap body length."""
        v = CONTROL_CHAR_RE.sub("", v)
        return v[:MAX_RAW_LENGTH]

    @field_validator("subject", mode="before")
    @classmethod
    def strip_subject(cls, v: str) -> str:
        """Strip control characters from subject line."""
        return CONTROL_CHAR_RE.sub("", v)

    @field_validator("sender_email", mode="before")
    @classmethod
    def validate_sender(cls, v: str) -> str:
        """Reject empty sender — required trust boundary check."""
        if not v or not v.strip():
            raise ValueError("sender_email must not be empty")
        return v


@dataclass
class SanitizationError:
    """Returned when sanitization fails — never raises."""

    reason: str
    raw_length: int


def sanitize_email(
    message_id: str,
    sender: str,
    subject: str,
    body: str,
) -> SanitizedIntent | SanitizationError:
    """Sanitize raw email fields into a validated SanitizedIntent.

    Returns SanitizationError if validation fails — never raises.

    This is the trust boundary gate (OWASP LLM01:2025):
    - Strips control characters from body and subject
    - Caps body at MAX_RAW_LENGTH characters
    - Rejects empty sender
    - Pure function: no I/O, no DB, no async
    """
    try:
        return SanitizedIntent(
            source_message_id=message_id,
            raw=body,
            sender_email=sender,
            subject=subject,
        )
    except Exception as exc:
        return SanitizationError(reason=str(exc), raw_length=len(body))
