"""Adapter registry — maps channel type strings to AdapterProtocol instances."""

from __future__ import annotations

from adapters.protocol import AdapterProtocol

__all__ = ["AdapterRegistry", "registry"]


class AdapterRegistry:
    """Maps channel_type strings to registered AdapterProtocol instances.

    Usage:
        registry.register("email", EmailAdapter(...))
        adapter = registry.get("email")
    """

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterProtocol] = {}

    def register(self, channel_type: str, adapter: AdapterProtocol) -> None:
        """Register an adapter for the given channel type."""
        self._adapters[channel_type] = adapter

    def get(self, channel_type: str) -> AdapterProtocol | None:
        """Return the registered adapter for channel_type, or None."""
        return self._adapters.get(channel_type)


# Module-level singleton — populated at app startup
registry = AdapterRegistry()
