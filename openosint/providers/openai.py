"""OpenAI provider adapter."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseProvider


def _tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


class OpenAIProvider(BaseProvider):
    """Wraps the OpenAI SDK for use in the OpenOSINT agent loop."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        try:
            import openai
        except ImportError as e:
            raise ImportError("openai package not installed — run: pip install openai") from e

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = openai.OpenAI(**kwargs)
        self.model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        openai_messages = [{"role": "system", "content": system}] + messages
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=openai_messages,
            tools=_tools_to_openai(tools),
            tool_choice="auto",
        )

        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments),
                    }
                )

        return {
            "stop_reason": "tool_use" if tool_calls else "end_turn",
            "text": msg.content or "",
            "tool_calls": tool_calls,
            "raw_content": msg,
            "raw": response,
        }

    def format_tool_results(
        self,
        tool_calls: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, default=str),
            }
            for tc, result in zip(tool_calls, results)
        ]
