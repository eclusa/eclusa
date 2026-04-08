"""
harness/message_format.py — Platform-neutral message history serialization.

MUST use ModelMessagesTypeAdapter (not provider-native format) to ensure
portability across model hot-swaps. D-03, D-24, D-25, Pitfall 3.
"""

from typing import Any

from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python


def serialize_history(messages: Any) -> list[dict]:
    """Convert pydantic-ai message list → JSONB-safe platform format.

    Always use this — never store raw ModelMessage objects or provider-native format.
    """
    return to_jsonable_python(messages)


def deserialize_history(data: list[dict]) -> Any:
    """Restore platform-format JSONB list → pydantic-ai message list for Agent.run().

    Works regardless of which model was used to produce the history. D-05.
    """
    return ModelMessagesTypeAdapter.validate_python(data)
