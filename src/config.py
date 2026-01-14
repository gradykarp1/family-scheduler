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

    # Calendar Provider
    calendar_provider: Literal["google", "local"] = Field(
        default="local",
        description="Calendar storage backend (google or local database)"
    )

    # Timezone Configuration
    timezone: str = Field(
        default="America/Los_Angeles",
        description="Default timezone for the family (IANA timezone name, e.g., America/Los_Angeles)"
    )

    # Google Calendar Configuration (Service Account - legacy)
    google_calendar_id: str = Field(
        default="",
        description="Google Calendar ID for the family calendar"
    )
    google_service_account_file: str = Field(
        default="",
        description="Path to Google service account JSON key file"
    )
    google_service_account_json: str = Field(
        default="",
        description="Google service account JSON (alternative to file, for deployments)"
    )

    # Google OAuth Configuration (for user calendars)
    google_oauth_client_id: str = Field(
        default="",
        description="Google OAuth 2.0 client ID"
    )
    google_oauth_client_secret: str = Field(
        default="",
        description="Google OAuth 2.0 client secret"
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/auth/google/callback",
        description="OAuth redirect URI (must match Google Cloud Console)"
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

    @property
    def uses_google_calendar(self) -> bool:
        """Check if Google Calendar is the configured provider."""
        return self.calendar_provider == "google"

    @property
    def uses_postgresql(self) -> bool:
        """Check if PostgreSQL is the configured database."""
        return "postgresql" in self.database_url.lower()

    @property
    def uses_google_oauth(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    def validate_production_config(self) -> None:
        """
        Validate configuration for production environment.

        Raises:
            ValueError: If required production settings are missing or invalid
        """
        if not self.is_production:
            return

        errors = []

        # PostgreSQL is required in production (SQLite doesn't persist on Vercel)
        if not self.uses_postgresql:
            errors.append(
                "Production requires PostgreSQL. "
                "Set DATABASE_URL to a PostgreSQL connection string."
            )

        # LLM API key is required
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required in production.")
        elif self.llm_provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required in production.")

        if errors:
            raise ValueError("Production configuration errors:\n- " + "\n- ".join(errors))

    def validate_google_calendar_config(self) -> None:
        """
        Validate Google Calendar configuration.

        Raises:
            ValueError: If required settings are missing
        """
        if not self.uses_google_calendar:
            return

        if not self.google_calendar_id:
            raise ValueError(
                "GOOGLE_CALENDAR_ID not configured. "
                "Please set it in your .env file."
            )

        if not self.google_service_account_file and not self.google_service_account_json:
            raise ValueError(
                "Google Calendar requires authentication. "
                "Set either GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON."
            )


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
