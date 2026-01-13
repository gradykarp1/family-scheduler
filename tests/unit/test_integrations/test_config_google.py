"""Tests for Google Calendar configuration settings."""

import pytest
from pydantic import ValidationError

from src.config import Settings


class TestCalendarProviderSettings:
    """Tests for calendar provider configuration."""

    def test_default_provider_is_local(self):
        """Should default to local storage."""
        settings = Settings()
        assert settings.calendar_provider == "local"
        assert settings.uses_google_calendar is False

    def test_google_provider(self):
        """Should support google provider."""
        settings = Settings(calendar_provider="google")
        assert settings.calendar_provider == "google"
        assert settings.uses_google_calendar is True

    def test_invalid_provider(self):
        """Should reject invalid provider."""
        with pytest.raises(ValidationError):
            Settings(calendar_provider="invalid")


class TestGoogleCalendarSettings:
    """Tests for Google Calendar specific settings."""

    def test_default_empty_values(self):
        """Should have empty defaults for Google settings."""
        settings = Settings()
        assert settings.google_calendar_id == ""
        assert settings.google_service_account_file == ""
        assert settings.google_service_account_json == ""

    def test_set_google_settings(self):
        """Should accept Google Calendar settings."""
        settings = Settings(
            google_calendar_id="family@group.calendar.google.com",
            google_service_account_file="/path/to/key.json",
        )

        assert settings.google_calendar_id == "family@group.calendar.google.com"
        assert settings.google_service_account_file == "/path/to/key.json"


class TestValidateGoogleCalendarConfig:
    """Tests for Google Calendar configuration validation."""

    def test_skip_validation_for_local_provider(self):
        """Should not validate Google settings for local provider."""
        settings = Settings(calendar_provider="local")
        # Should not raise
        settings.validate_google_calendar_config()

    def test_missing_calendar_id(self):
        """Should raise error if calendar ID missing for Google provider."""
        settings = Settings(
            calendar_provider="google",
            google_service_account_file="/path/to/key.json",
        )

        with pytest.raises(ValueError) as exc_info:
            settings.validate_google_calendar_config()

        assert "GOOGLE_CALENDAR_ID not configured" in str(exc_info.value)

    def test_missing_authentication(self):
        """Should raise error if no auth method configured."""
        settings = Settings(
            calendar_provider="google",
            google_calendar_id="family@group.calendar.google.com",
        )

        with pytest.raises(ValueError) as exc_info:
            settings.validate_google_calendar_config()

        assert "authentication" in str(exc_info.value).lower()

    def test_valid_with_service_account_file(self):
        """Should pass with calendar ID and service account file."""
        settings = Settings(
            calendar_provider="google",
            google_calendar_id="family@group.calendar.google.com",
            google_service_account_file="/path/to/key.json",
        )

        # Should not raise
        settings.validate_google_calendar_config()

    def test_valid_with_service_account_json(self):
        """Should pass with calendar ID and service account JSON."""
        settings = Settings(
            calendar_provider="google",
            google_calendar_id="family@group.calendar.google.com",
            google_service_account_json='{"type": "service_account"}',
        )

        # Should not raise
        settings.validate_google_calendar_config()
