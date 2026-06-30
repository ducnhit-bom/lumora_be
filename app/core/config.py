import os
from dataclasses import dataclass, field
from functools import lru_cache


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Lumora API"))
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://lumora:lumora@localhost:5432/lumora",
        ),
    )
    cors_origins: list[str] = field(default_factory=lambda: _csv_env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS))


@lru_cache
def get_settings() -> Settings:
    return Settings()
