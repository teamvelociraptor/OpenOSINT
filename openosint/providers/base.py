"""Abstract base class for AI provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Common interface for Anthropic, OpenAI, and Ollama providers."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Send a completion request and return a normalized response dict.

        Returns a dict with keys:
            stop_reason: "end_turn" | "tool_use"
            text: str (final assistant text, if stop_reason == "end_turn")
            tool_calls: list[dict] with keys name, id, input
            raw: the original API response object
        """

    @abstractmethod
    def format_tool_results(
        self,
        tool_calls: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return a message dict representing tool results for the next request."""
