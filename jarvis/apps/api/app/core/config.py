from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Runtime configuration. Secrets remain server-side and are never logged."""
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_prefix="JARVIS_", case_sensitive=False)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
