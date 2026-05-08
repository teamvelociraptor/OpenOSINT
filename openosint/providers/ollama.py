"""Ollama provider adapter (uses OpenAI-compatible API)."""

from __future__ import annotations

from typing import Any

from .openai import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """Ollama local LLM provider — reuses the OpenAI-compatible API path."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        super().__init__(
            api_key="ollama",
            model=model,
            base_url=f"{base_url}/v1",
        )
