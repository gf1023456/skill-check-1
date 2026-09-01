"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass, field
from typing import List, Optional


def _optional_env(name: str) -> Optional[str]:
    return os.getenv(name) or None


def _csv_env(name: str) -> List[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    openai_api_key: Optional[str] = field(default_factory=lambda: _optional_env("OPENAI_API_KEY"))
    deepseek_url: Optional[str] = field(default_factory=lambda: _optional_env("DEEPSEEK_URL"))
    deepseek_api_key: Optional[str] = field(default_factory=lambda: _optional_env("DEEPSEEK_API_KEY"))
    azure_api_base: Optional[str] = field(default_factory=lambda: _optional_env("AZURE_API_BASE"))
    azure_api_key: Optional[str] = field(default_factory=lambda: _optional_env("AZURE_API_KEY"))
    azure_deployment: Optional[str] = field(default_factory=lambda: _optional_env("AZURE_DEPLOYMENT"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: _optional_env("ANTHROPIC_API_KEY"))
    anthropic_url: Optional[str] = field(default_factory=lambda: _optional_env("ANTHROPIC_URL"))
    local_llm_url: Optional[str] = field(default_factory=lambda: _optional_env("LOCAL_LLM_URL"))
    allow_private_network: bool = field(default_factory=lambda: os.getenv("ALLOW_PRIVATE_NETWORK", "false").lower() == "true")
    allowed_hosts: List[str] = field(default_factory=lambda: _csv_env("ALLOWED_HOSTS"))
    storage_dir: str = field(default_factory=lambda: os.getenv("STORAGE_DIR", "/tmp/skill_checker_storage"))


settings = Settings()
