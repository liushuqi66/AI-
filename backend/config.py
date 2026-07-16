"""Application configuration loaded from environment variables.

Provides a singleton Config instance that reads all settings
from .env file and environment variables with sensible defaults.

Usage:
    from config import config
    api_key = config.OPENAI_API_KEY
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable application configuration.

    All values are read from environment variables with
    fallback defaults. The dataclass is frozen to prevent
    accidental modification at runtime.
    """

    # ── AI Model Configuration ─────────────────────────────
    OPENAI_API_KEY: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    OPENAI_BASE_URL: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    AI_MODEL: str = field(
        default_factory=lambda: os.getenv("AI_MODEL", "gpt-4o-mini")
    )

    # ── Redis Cache Configuration ──────────────────────────
    REDIS_HOST: str = field(
        default_factory=lambda: os.getenv("REDIS_HOST", "localhost")
    )
    REDIS_PORT: int = field(
        default_factory=lambda: int(os.getenv("REDIS_PORT", "6379"))
    )
    REDIS_PASSWORD: Optional[str] = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD") or None
    )
    REDIS_DB: int = field(
        default_factory=lambda: int(os.getenv("REDIS_DB", "0"))
    )

    # ── Flask Settings ─────────────────────────────────────
    MAX_CONTENT_LENGTH: int = field(
        default_factory=lambda: int(
            os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024))  # 16 MB
        )
    )
    FLASK_PORT: int = field(
        default_factory=lambda: int(os.getenv("FLASK_PORT", "5000"))
    )
    FLASK_ENV: str = field(
        default_factory=lambda: os.getenv("FLASK_ENV", "production")
    )

    # ── Cache TTL (seconds) ────────────────────────────────
    CACHE_TTL: int = 3600  # 1 hour

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.FLASK_ENV == "development"

    @property
    def is_ai_configured(self) -> bool:
        """Check if AI API key is configured."""
        return bool(self.OPENAI_API_KEY)


# Singleton configuration instance
config = Config()
