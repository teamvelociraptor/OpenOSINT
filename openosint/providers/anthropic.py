"""Anthropic (Claude) provider adapter."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    """Wraps the Anthropic SDK for use in the OpenOSINT agent loop."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("anthropic package not installed — run: pip install anthropic") from e

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        text = ""
        tool_calls = []

        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {"id": block.id, "name": block.name, "input": block.input}
                )

        return {
            "stop_reason": response.stop_reason,
            "text": text,
            "tool_calls": tool_calls,
            "raw_content": response.content,
            "raw": response,
        }

    def format_tool_results(
        self,
        tool_calls: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": json.dumps(result, default=str),
                }
                for tc, result in zip(tool_calls, results)
            ],
        }
