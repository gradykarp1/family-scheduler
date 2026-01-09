"""
Configuration management for Family Scheduler.

Uses Pydantic Settings for type-safe environment variable loading.
Configured via .env file in project root.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be configured via .env file or environment variables.
    See .env.example for available options.
    """

    # Python & Application
    python_env: Literal["development", "production"] = Field(
        default="development",
        description="Application environment"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./data/family_scheduler.db",
        description="Database connection URL"
    )

    # LLM Provider
    llm_provider: Literal["anthropic", "openai"] = Field(
        default="anthropic",
        description="LLM provider to use for agents"
    )
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key"
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key"
    )

    # LangSmith (optional observability)
    langsmith_api_key: str = Field(
        default="",
        description="LangSmith API key for tracing"
    )
    langsmith_project: str = Field(
        default="family-scheduler-dev",
        description="LangSmith project name"
    )
    langsmith_tracing_v2: bool = Field(
        default=False,
        description="Enable LangSmith tracing"
    )

    # API Configuration
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8000,
        description="API server port"
    )
    api_reload: bool = Field(
        default=True,
        description="Enable auto-reload in development"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.python_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.python_env == "production"

    def get_llm_api_key(self) -> str:
        """
        Get the API key for the configured LLM provider.

        Returns:
            API key for the active LLM provider

        Raises:
            ValueError: If the API key is not configured
        """
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not configured. "
                    "Please set it in your .env file."
                )
            return self.anthropic_api_key
        elif self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY not configured. "
                    "Please set it in your .env file."
                )
            return self.openai_api_key
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This function is cached to ensure we only load settings once.
    Use this function throughout the application to access settings.

    Returns:
        Settings instance loaded from environment

    Example:
        >>> from src.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.database_url)
    """
    return Settings()
