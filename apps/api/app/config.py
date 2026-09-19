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
    gemini_model: str | None = None
    groq_api_key: str | None = Field(default=None, repr=False)
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_api_key: str | None = Field(default=None, repr=False)
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    ai_provider: str = "gemini"
    ai_model: str = "gemini-2.5-flash"
    ai_timeout_seconds: float = 30.0
    conversation_context_messages: int = 20
    cors_origins: list[str] = ["http://localhost:3000"]
    session_hours: int = 168
    workspace_root: str = "./workspace"
    trading_mode: str = "PAPER"
    trading_initial_balance: float = 10000.0
    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_trades_per_day: int = 5
    min_confidence: float = 0.60
    min_risk_reward: float = 1.5
    max_drawdown: float = 0.10
    data_provider: str = "simulated"


@lru_cache
def get_settings() -> Settings:
    return Settings()
