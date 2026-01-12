"""
Unit tests for src/config.py

Tests Settings class, environment variable loading, API key validation,
and configuration caching behavior.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import Settings, get_settings


class TestSettingsDefaults:
    """Test Settings initialization with default values."""

    def test_settings_defaults(self, monkeypatch):
        """Settings should initialize with correct default values."""
        # Clear env vars to test defaults
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        # Prevent loading from .env file by pointing to non-existent file
        with patch("pydantic_settings.BaseSettings.model_config") as mock_config:
            mock_config.return_value = {"env_file": None}
            settings = Settings(_env_file=None)

        assert settings.python_env == "development"
        assert settings.log_level == "INFO"
        assert settings.database_url == "sqlite:///./data/family_scheduler.db"
        assert settings.llm_provider == "anthropic"
        assert settings.anthropic_api_key == ""
        assert settings.openai_api_key == ""
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.api_reload is True
        assert settings.langsmith_tracing_v2 is False

    def test_is_development_default(self):
        """is_development should return True by default."""
        settings = Settings()
        assert settings.is_development is True
        assert settings.is_production is False

    def test_is_production_when_set(self):
        """is_production should return True when python_env is production."""
        settings = Settings(python_env="production")
        assert settings.is_production is True
        assert settings.is_development is False


class TestSettingsEnvironmentVariables:
    """Test Settings loading from environment variables."""

    def test_settings_from_env_vars(self, monkeypatch):
        """Settings should load values from environment variables."""
        monkeypatch.setenv("PYTHON_ENV", "production")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        monkeypatch.setenv("API_PORT", "9000")

        settings = Settings()

        assert settings.python_env == "production"
        assert settings.log_level == "DEBUG"
        assert settings.database_url == "postgresql://localhost/test"
        assert settings.llm_provider == "openai"
        assert settings.anthropic_api_key == "sk-ant-test-key"
        assert settings.api_port == 9000

    def test_settings_case_insensitive(self, monkeypatch):
        """Settings should accept case-insensitive environment variable names."""
        # Pydantic Settings is case-insensitive for env var names, not values
        monkeypatch.setenv("python_env", "production")
        monkeypatch.setenv("log_level", "ERROR")  # Value must match literal exactly

        settings = Settings()

        assert settings.python_env == "production"
        assert settings.log_level == "ERROR"

    def test_settings_with_langsmith_config(self, monkeypatch):
        """Settings should load LangSmith configuration."""
        monkeypatch.setenv("LANGSMITH_API_KEY", "ls_test_key")
        monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")
        monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")

        settings = Settings()

        assert settings.langsmith_api_key == "ls_test_key"
        assert settings.langsmith_project == "test-project"
        assert settings.langsmith_tracing_v2 is True


class TestSettingsValidation:
    """Test Settings field validation."""

    def test_invalid_python_env(self):
        """Settings should reject invalid python_env values."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(python_env="invalid")

        error = exc_info.value.errors()[0]
        assert error["type"] == "literal_error"
        assert "python_env" in str(error)

    def test_invalid_log_level(self):
        """Settings should reject invalid log_level values."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(log_level="INVALID")

        error = exc_info.value.errors()[0]
        assert error["type"] == "literal_error"

    def test_invalid_llm_provider(self):
        """Settings should reject invalid llm_provider values."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(llm_provider="invalid")

        error = exc_info.value.errors()[0]
        assert error["type"] == "literal_error"

    def test_invalid_api_port(self):
        """Settings should reject non-integer api_port values."""
        with pytest.raises(ValidationError):
            Settings(api_port="not_a_number")


class TestGetLLMAPIKey:
    """Test get_llm_api_key() method with different providers."""

    def test_get_anthropic_api_key_success(self):
        """get_llm_api_key should return Anthropic key when provider is anthropic."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test-key-123"
        )

        api_key = settings.get_llm_api_key()

        assert api_key == "sk-ant-test-key-123"

    def test_get_anthropic_api_key_missing(self):
        """get_llm_api_key should raise ValueError when Anthropic key is missing."""
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key=""
        )

        with pytest.raises(ValueError) as exc_info:
            settings.get_llm_api_key()

        assert "ANTHROPIC_API_KEY not configured" in str(exc_info.value)
        assert ".env file" in str(exc_info.value)

    def test_get_openai_api_key_success(self):
        """get_llm_api_key should return OpenAI key when provider is openai."""
        settings = Settings(
            llm_provider="openai",
            openai_api_key="sk-openai-test-key-456"
        )

        api_key = settings.get_llm_api_key()

        assert api_key == "sk-openai-test-key-456"

    def test_get_openai_api_key_missing(self):
        """get_llm_api_key should raise ValueError when OpenAI key is missing."""
        settings = Settings(
            llm_provider="openai",
            openai_api_key=""
        )

        with pytest.raises(ValueError) as exc_info:
            settings.get_llm_api_key()

        assert "OPENAI_API_KEY not configured" in str(exc_info.value)
        assert ".env file" in str(exc_info.value)

    # Note: Testing unknown provider is not possible since Pydantic validation
    # prevents invalid llm_provider values at Settings initialization time.
    # This is the desired behavior - fail fast on configuration errors.


class TestGetSettingsCaching:
    """Test get_settings() function and LRU cache behavior."""

    def test_get_settings_returns_settings_instance(self):
        """get_settings() should return a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_cached(self):
        """get_settings() should return the same instance on multiple calls."""
        # Clear the cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the exact same object due to @lru_cache
        assert settings1 is settings2

    def test_get_settings_cache_info(self):
        """get_settings() cache should track hits and misses."""
        get_settings.cache_clear()

        # First call - cache miss
        get_settings()
        info1 = get_settings.cache_info()
        assert info1.misses == 1
        assert info1.hits == 0

        # Second call - cache hit
        get_settings()
        info2 = get_settings.cache_info()
        assert info2.misses == 1
        assert info2.hits == 1

    def test_get_settings_cache_clear(self):
        """get_settings.cache_clear() should reset the cache."""
        get_settings.cache_clear()

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # After cache clear, should get a new instance
        # (May be equal in value but not the same object)
        cache_info = get_settings.cache_info()
        assert cache_info.currsize == 1  # Only one item in cache after clear


class TestSettingsIntegration:
    """Integration tests combining multiple Settings features."""

    def test_production_config_with_anthropic(self, monkeypatch):
        """Test production configuration with Anthropic provider."""
        monkeypatch.setenv("PYTHON_ENV", "production")
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-prod-key")
        monkeypatch.setenv("API_RELOAD", "false")
        monkeypatch.setenv("DATABASE_URL", "postgresql://prod-db:5432/scheduler")

        settings = Settings()

        assert settings.is_production is True
        assert settings.log_level == "WARNING"
        assert settings.api_reload is False
        assert settings.get_llm_api_key() == "sk-ant-prod-key"
        assert settings.database_url == "postgresql://prod-db:5432/scheduler"

    def test_development_config_with_openai(self, monkeypatch):
        """Test development configuration with OpenAI provider."""
        monkeypatch.setenv("PYTHON_ENV", "development")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-dev-key")

        settings = Settings()

        assert settings.is_development is True
        assert settings.log_level == "DEBUG"
        assert settings.api_reload is True
        assert settings.get_llm_api_key() == "sk-openai-dev-key"

    def test_settings_with_all_optional_fields(self, monkeypatch):
        """Test Settings with all optional fields configured."""
        monkeypatch.setenv("PYTHON_ENV", "production")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-key")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
        monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")
        monkeypatch.setenv("LANGSMITH_PROJECT", "prod-project")
        monkeypatch.setenv("LANGSMITH_TRACING_V2", "true")

        settings = Settings()

        assert settings.anthropic_api_key == "sk-ant-key"
        assert settings.openai_api_key == "sk-openai-key"
        assert settings.langsmith_api_key == "ls-key"
        assert settings.langsmith_project == "prod-project"
        assert settings.langsmith_tracing_v2 is True
