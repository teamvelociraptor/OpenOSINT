"""Configuration management for OpenOSINT."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".config" / "openosint"
CONFIG_FILE = CONFIG_DIR / "config.json"

PROVIDER_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "ollama": "llama3.1",
}


@dataclass
class Config:
    provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    model: str = ""

    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    hibp_api_key: Optional[str] = None
    abuseipdb_api_key: Optional[str] = None

    ollama_base_url: str = "http://localhost:11434"

    max_tokens: int = 8192
    max_iterations: int = 25

    save_reports: bool = True
    reports_dir: str = "reports"

    def __post_init__(self) -> None:
        if not self.model:
            self.model = PROVIDER_MODELS.get(self.provider, "claude-sonnet-4-20250514")

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()

        config = cls()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except (json.JSONDecodeError, OSError):
                pass

        # Environment variables always win
        if v := os.getenv("ANTHROPIC_API_KEY"):
            config.anthropic_api_key = v
        if v := os.getenv("OPENAI_API_KEY"):
            config.openai_api_key = v
        if v := os.getenv("HIBP_API_KEY"):
            config.hibp_api_key = v
        if v := os.getenv("ABUSEIPDB_API_KEY"):
            config.abuseipdb_api_key = v
        if v := os.getenv("OPENOSINT_PROVIDER"):
            config.provider = v  # type: ignore[assignment]
        if v := os.getenv("OPENOSINT_MODEL"):
            config.model = v
        if v := os.getenv("OLLAMA_BASE_URL"):
            config.ollama_base_url = v

        if not config.model:
            config.model = PROVIDER_MODELS.get(config.provider, "claude-sonnet-4-20250514")

        return config

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "provider": self.provider,
            "model": self.model,
            "ollama_base_url": self.ollama_base_url,
            "max_tokens": self.max_tokens,
            "max_iterations": self.max_iterations,
            "save_reports": self.save_reports,
            "reports_dir": self.reports_dir,
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.provider == "anthropic" and not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is not set (export it or add to .env)")
        elif self.provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is not set (export it or add to .env)")
        return errors

    @property
    def active_api_key(self) -> Optional[str]:
        if self.provider == "anthropic":
            return self.anthropic_api_key
        if self.provider == "openai":
            return self.openai_api_key
        return None
