"""Application configuration loaded from environment / .env.

All settings are environment-driven so no machine-specific paths or secrets are baked into
the codebase (the repo is public). See `.env.example` for the full list.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "staging", "prod"]
# mock = offline; claude_cli = local Claude CLI on the Pro/Max subscription (no API bill);
# claude = paid Anthropic API; openai = future.
LLMProviderName = Literal["mock", "claude_cli", "claude", "openai"]


class Settings(BaseSettings):
    """Typed application settings.

    Defaults are chosen so the app runs fully offline with mocked integrations and a local
    SQLite database — no secrets required for development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_env: Environment = "dev"
    log_level: str = "INFO"
    # bind-all is intended for the containerized API
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000

    # Database
    database_url: str = "sqlite:///./pocket_dev.sqlite3"

    # Queue / cache
    redis_url: str | None = "redis://localhost:6379/0"

    # Media store
    media_root: str = "./data/media"
    media_max_bytes: int = 53_687_091_200  # 50 GB
    audio_retention_days: int = 30

    # Security
    device_token_pepper: str = "dev-insecure-pepper-change-me"
    session_ttl_minutes: int = 15
    dev_session_pin: str = "0000"

    # LLM
    llm_provider: LLMProviderName = "mock"
    llm_model: str | None = None
    llm_api_key: str | None = None
    # Path to the `claude` CLI used by the claude_cli provider (subscription auth).
    claude_cli_path: str = "claude"

    # Integrations
    gmail_provider: Literal["mock", "google"] = "mock"
    gmail_default_window_days: int = 1
    calendar_provider: Literal["mock", "ics_feed"] = "mock"
    calendar_ics_feed_url: str | None = None
    work_hours_start: int = 9
    work_hours_end: int = 17
    github_provider: Literal["mock", "github"] = "mock"
    github_token: str | None = None
    github_repo_allowlist: str = ""
    claude_code_provider: Literal["mock", "real"] = "mock"

    # Daily summary
    morning_summary_start_hour: int = 5

    # Approval policy
    require_approval_all: bool = True

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def github_repo_allowlist_set(self) -> frozenset[str]:
        return frozenset(
            repo.strip() for repo in self.github_repo_allowlist.split(",") if repo.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one read of the environment per process)."""
    return Settings()
