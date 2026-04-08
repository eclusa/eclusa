"""
judgment/context_prep.py — Local context preparation for judgment passes.

No model call. Strips tool noise, summarizes long middles, foregrounds
decisions. Runs on executor. JUDG-03, D-13, D-14.
"""

import logging

logger = logging.getLogger(__name__)


def prepare_context(message_history: list[dict], max_chars: int = 8000) -> str:
    """Prepare message history for judgment pass consumption.

    Strips tool call noise (kind='tool-call', kind='tool-return').
    Keeps user requests and model text responses.
    Truncates long middles: keep first 20% + last 60% if over max_chars.

    Returns a plain text string — the judgment prompt prefix.
    """
    # Extract readable messages only
    readable = []
    for msg in message_history:
        kind = msg.get("kind", "")
        if kind in ("tool-call", "tool-return"):
            continue  # strip noise
        role = "User" if kind == "request" else "Assistant"
        # Extract text content — may be list of parts or plain string
        content = msg.get("content", "")
        if isinstance(content, list):
            # pydantic-ai platform format: content is list of part dicts
            parts = [
                p.get("content", "")
                for p in content
                if isinstance(p, dict) and "content" in p
            ]
            text = " ".join(str(p) for p in parts if p)
        else:
            text = str(content)
        if text.strip():
            readable.append(f"{role}: {text.strip()}")

    full_text = "\n\n".join(readable)

    if len(full_text) <= max_chars:
        return full_text

    # Truncate: keep first 20% and last 60%
    keep_start = int(max_chars * 0.20)
    keep_end = int(max_chars * 0.60)
    truncated = (
        full_text[:keep_start]
        + f"\n\n[... {len(full_text) - keep_start - keep_end} chars omitted ...]\n\n"
        + full_text[-keep_end:]
    )
    logger.debug(
        "Context truncated from %d to %d chars", len(full_text), len(truncated)
    )
    return truncated
