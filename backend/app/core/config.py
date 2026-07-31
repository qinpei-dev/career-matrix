"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and the root .env file."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(min_length=1)
    demo_auth_tokens: dict[str, str] = Field(default_factory=dict)
    document_storage_path: Path = PROJECT_ROOT / "data" / "documents"
    embedding_provider: str = "openai_compatible"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = Field(default=1024, gt=0)
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    agent_run_timeout_seconds: float = Field(default=120.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
