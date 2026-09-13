from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        extra="ignore",
    )
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./jarvis.db"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    ai_provider: str = "gemini"
    ai_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: float = 30.0
    conversation_context_messages: int = 20
    cors_origins: list[str] = ["http://localhost:3000"]
    session_hours: int = 168
    workspace_root: str = "./workspace"


@lru_cache
def get_settings() -> Settings:
    return Settings()
