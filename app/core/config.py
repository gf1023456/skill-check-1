from pydantic import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # LLM / provider settings
    llm_provider: str = "openai"  # openai | deepseek | anthropic | azure | local
    openai_api_key: Optional[str] = None
    deepseek_url: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    # Azure OpenAI
    azure_api_base: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_deployment: Optional[str] = None
    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_url: Optional[str] = None
    # Local/custom LLM endpoint (expects POST {"prompt": ...})
    local_llm_url: Optional[str] = None

    # Sandbox / network settings
    allow_private_network: bool = False
    allowed_hosts: List[str] = []

    # Work directories
    storage_dir: str = "/tmp/skill_checker_storage"

    class Config:
        env_file = ".env"

settings = Settings()