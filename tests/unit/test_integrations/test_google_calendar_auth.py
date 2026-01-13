"""Tests for Google Calendar authentication."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.google_calendar.auth import (
    CALENDAR_SCOPES,
    GoogleAuthManager,
    get_service_account_credentials,
    get_service_account_credentials_from_env,
)
from src.integrations.google_calendar.exceptions import GoogleCalendarAuthError


class TestServiceAccountCredentials:
    """Tests for service account credential loading."""

    def test_missing_both_file_and_info(self):
        """Should raise error if neither file nor info provided."""
        with pytest.raises(GoogleCalendarAuthError) as exc_info:
            get_service_account_credentials()

        assert "service_account_file or service_account_info must be provided" in str(exc_info.value)

    def test_file_not_found(self):
        """Should raise error if service account file doesn't exist."""
        with pytest.raises(GoogleCalendarAuthError) as exc_info:
            get_service_account_credentials(service_account_file="/nonexistent/path.json")

        assert "Service account file not found" in str(exc_info.value)

    @patch("src.integrations.google_calendar.auth.service_account.Credentials")
    def test_load_from_info(self, mock_credentials_class):
        """Should load credentials from dict."""
        mock_creds = MagicMock()
        mock_creds.service_account_email = "test@project.iam.gserviceaccount.com"
        mock_credentials_class.from_service_account_info.return_value = mock_creds

        service_account_info = {
            "type": "service_account",
            "project_id": "test-project",
            "client_email": "test@project.iam.gserviceaccount.com",
        }

        result = get_service_account_credentials(service_account_info=service_account_info)

        mock_credentials_class.from_service_account_info.assert_called_once_with(
            service_account_info,
            scopes=CALENDAR_SCOPES,
        )
        assert result == mock_creds

    @patch("src.integrations.google_calendar.auth.service_account.Credentials")
    def test_load_from_file(self, mock_credentials_class):
        """Should load credentials from file path."""
        mock_creds = MagicMock()
        mock_creds.service_account_email = "test@project.iam.gserviceaccount.com"
        mock_credentials_class.from_service_account_file.return_value = mock_creds

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "service_account"}, f)
            temp_path = f.name

        try:
            result = get_service_account_credentials(service_account_file=temp_path)

            mock_credentials_class.from_service_account_file.assert_called_once_with(
                temp_path,
                scopes=CALENDAR_SCOPES,
            )
            assert result == mock_creds
        finally:
            os.unlink(temp_path)

    @patch("src.integrations.google_calendar.auth.service_account.Credentials")
    def test_wraps_unexpected_errors(self, mock_credentials_class):
        """Should wrap unexpected errors in GoogleCalendarAuthError."""
        mock_credentials_class.from_service_account_info.side_effect = ValueError("Invalid key")

        with pytest.raises(GoogleCalendarAuthError) as exc_info:
            get_service_account_credentials(service_account_info={"type": "service_account"})

        assert "Failed to load service account credentials" in str(exc_info.value)
        assert exc_info.value.original_error is not None


class TestServiceAccountCredentialsFromEnv:
    """Tests for loading credentials from environment variable."""

    def test_env_var_not_set(self):
        """Should raise error if env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GoogleCalendarAuthError) as exc_info:
                get_service_account_credentials_from_env("NONEXISTENT_VAR")

            assert "not set or empty" in str(exc_info.value)

    def test_invalid_json(self):
        """Should raise error for invalid JSON."""
        with patch.dict(os.environ, {"TEST_VAR": "not valid json"}):
            with pytest.raises(GoogleCalendarAuthError) as exc_info:
                get_service_account_credentials_from_env("TEST_VAR")

            assert "Invalid JSON" in str(exc_info.value)

    @patch("src.integrations.google_calendar.auth.get_service_account_credentials")
    def test_valid_json(self, mock_get_creds):
        """Should parse JSON and delegate to get_service_account_credentials."""
        mock_creds = MagicMock()
        mock_get_creds.return_value = mock_creds

        json_str = json.dumps({"type": "service_account", "project_id": "test"})

        with patch.dict(os.environ, {"TEST_VAR": json_str}):
            result = get_service_account_credentials_from_env("TEST_VAR")

        mock_get_creds.assert_called_once_with(
            service_account_info={"type": "service_account", "project_id": "test"}
        )
        assert result == mock_creds


class TestGoogleAuthManager:
    """Tests for GoogleAuthManager class."""

    @patch("src.integrations.google_calendar.auth.get_service_account_credentials")
    def test_get_credentials_lazy_loading(self, mock_get_creds):
        """Should load credentials only when first accessed."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_get_creds.return_value = mock_creds

        manager = GoogleAuthManager(service_account_file="/path/to/key.json")

        # Credentials not loaded yet
        mock_get_creds.assert_not_called()

        # First access loads credentials
        creds1 = manager.get_credentials()
        mock_get_creds.assert_called_once()
        assert creds1 == mock_creds

        # Second access returns cached credentials
        creds2 = manager.get_credentials()
        assert mock_get_creds.call_count == 1
        assert creds2 == mock_creds

    @patch("src.integrations.google_calendar.auth.get_service_account_credentials")
    def test_credentials_refresh_when_expired(self, mock_get_creds):
        """Should refresh credentials if expired."""
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_get_creds.return_value = mock_creds

        manager = GoogleAuthManager(service_account_file="/path/to/key.json")
        manager.get_credentials()

        mock_creds.refresh.assert_called_once_with(None)

    @patch("src.integrations.google_calendar.auth.get_service_account_credentials")
    def test_service_account_email_property(self, mock_get_creds):
        """Should return service account email."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.service_account_email = "test@project.iam.gserviceaccount.com"
        mock_get_creds.return_value = mock_creds

        manager = GoogleAuthManager(service_account_file="/path/to/key.json")

        assert manager.service_account_email == "test@project.iam.gserviceaccount.com"

    @patch("src.integrations.google_calendar.auth.get_service_account_credentials")
    def test_service_account_email_none_for_non_service_account(self, mock_get_creds):
        """Should return None if credentials don't have service_account_email."""
        mock_creds = MagicMock(spec=[])  # No service_account_email attribute
        mock_creds.expired = False
        mock_get_creds.return_value = mock_creds

        manager = GoogleAuthManager(service_account_file="/path/to/key.json")

        assert manager.service_account_email is None

    def test_init_with_file_and_info(self):
        """Should accept both file and info parameters."""
        manager = GoogleAuthManager(
            service_account_file="/path/to/key.json",
            service_account_info={"type": "service_account"},
        )

        assert manager._service_account_file == "/path/to/key.json"
        assert manager._service_account_info == {"type": "service_account"}
