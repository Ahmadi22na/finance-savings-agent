"""Module documentation."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "Rasheed - Finance Savings Agent"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql://rasheed_user:rasheed_pass@db:5432/rasheed_db"

    # --- Auth / JWT ---
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30






    GEMINI_API_KEY: str = ""
    AGENT_MODEL: str = "gemini-3.6-flash"
    AGENT_DEFAULT_NAME: str = "رشيد"

    # --- CORS ---
    ALLOWED_ORIGINS: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    """Get settings documentation."""
    return Settings()


settings = get_settings()
