"""
Authentication for Google Calendar API.

Supports:
- Service account authentication (recommended for shared calendars)
- OAuth 2.0 user authentication (for individual calendars - future)
"""

import json
import logging
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

from src.integrations.google_calendar.exceptions import GoogleCalendarAuthError

logger = logging.getLogger(__name__)

# Required scopes for calendar operations
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_service_account_credentials(
    service_account_file: Optional[str] = None,
    service_account_info: Optional[dict] = None,
) -> Credentials:
    """
    Get credentials from a service account.

    Service account is recommended for shared family calendars.
    The calendar must be shared with the service account email.

    Args:
        service_account_file: Path to service account JSON key file
        service_account_info: Service account info as dict (alternative to file)

    Returns:
        Google credentials object

    Raises:
        GoogleCalendarAuthError: If credentials cannot be loaded
    """
    try:
        if service_account_info:
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=CALENDAR_SCOPES,
            )
        elif service_account_file:
            file_path = Path(service_account_file)
            if not file_path.exists():
                raise GoogleCalendarAuthError(
                    f"Service account file not found: {service_account_file}"
                )
            credentials = service_account.Credentials.from_service_account_file(
                str(file_path),
                scopes=CALENDAR_SCOPES,
            )
        else:
            raise GoogleCalendarAuthError(
                "Either service_account_file or service_account_info must be provided"
            )

        logger.info(
            f"Loaded service account credentials: {credentials.service_account_email}"
        )
        return credentials

    except Exception as e:
        if isinstance(e, GoogleCalendarAuthError):
            raise
        raise GoogleCalendarAuthError(
            f"Failed to load service account credentials: {e}",
            original_error=e,
        )


def get_service_account_credentials_from_env(
    env_var: str = "GOOGLE_SERVICE_ACCOUNT_JSON",
) -> Credentials:
    """
    Get credentials from environment variable containing JSON.

    Useful for deployment where file system access is limited.

    Args:
        env_var: Environment variable name containing JSON string

    Returns:
        Google credentials object

    Raises:
        GoogleCalendarAuthError: If credentials cannot be loaded
    """
    import os

    json_str = os.getenv(env_var)
    if not json_str:
        raise GoogleCalendarAuthError(
            f"Environment variable {env_var} not set or empty"
        )

    try:
        service_account_info = json.loads(json_str)
        return get_service_account_credentials(service_account_info=service_account_info)
    except json.JSONDecodeError as e:
        raise GoogleCalendarAuthError(
            f"Invalid JSON in {env_var}: {e}",
            original_error=e,
        )


class GoogleAuthManager:
    """
    Manages Google Calendar authentication.

    Provides a unified interface for different auth methods.
    """

    def __init__(
        self,
        service_account_file: Optional[str] = None,
        service_account_info: Optional[dict] = None,
    ):
        """
        Initialize auth manager.

        Args:
            service_account_file: Path to service account JSON key file
            service_account_info: Service account info as dict
        """
        self._credentials: Optional[Credentials] = None
        self._service_account_file = service_account_file
        self._service_account_info = service_account_info

    def get_credentials(self) -> Credentials:
        """
        Get valid credentials, loading or refreshing as needed.

        Returns:
            Valid Google credentials
        """
        if self._credentials is None:
            self._credentials = get_service_account_credentials(
                service_account_file=self._service_account_file,
                service_account_info=self._service_account_info,
            )

        # Service account credentials auto-refresh, but check if expired
        if self._credentials.expired:
            self._credentials.refresh(None)

        return self._credentials

    @property
    def service_account_email(self) -> Optional[str]:
        """Get the service account email for sharing calendars."""
        creds = self.get_credentials()
        if hasattr(creds, "service_account_email"):
            return creds.service_account_email
        return None
