"""
Authentication for Google Calendar API.

Supports:
- Service account authentication (for shared calendars managed by the app)
- OAuth 2.0 user authentication (for individual user calendars)
"""

import json
import logging
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

from src.config import get_settings
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


def get_oauth_credentials(
    access_token: str,
    refresh_token: Optional[str] = None,
    token_uri: str = "https://oauth2.googleapis.com/token",
    scopes: Optional[list[str]] = None,
) -> Credentials:
    """
    Create credentials from OAuth tokens.

    Used for accessing user's personal calendar after OAuth flow.

    Args:
        access_token: Valid access token
        refresh_token: Refresh token for automatic renewal (optional)
        token_uri: Google's token endpoint
        scopes: OAuth scopes (optional)

    Returns:
        Google credentials object
    """
    settings = get_settings()

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=scopes or CALENDAR_SCOPES,
    )


def get_oauth_credentials_from_dict(credentials_dict: dict) -> Credentials:
    """
    Create credentials from a dictionary.

    This is convenient when loading stored credentials from the database.

    Args:
        credentials_dict: Dict with keys: token, refresh_token, token_uri, scopes

    Returns:
        Google credentials object
    """
    return get_oauth_credentials(
        access_token=credentials_dict["token"],
        refresh_token=credentials_dict.get("refresh_token"),
        token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
        scopes=credentials_dict.get("scopes"),
    )


class GoogleAuthManager:
    """
    Manages Google Calendar authentication.

    Provides a unified interface for different auth methods:
    - Service account: For shared/system calendars
    - OAuth: For user's personal calendars
    """

    def __init__(
        self,
        service_account_file: Optional[str] = None,
        service_account_info: Optional[dict] = None,
        oauth_credentials: Optional[dict] = None,
    ):
        """
        Initialize auth manager.

        Args:
            service_account_file: Path to service account JSON key file
            service_account_info: Service account info as dict
            oauth_credentials: OAuth credentials dict (token, refresh_token, etc.)

        Note: Provide either service account OR oauth credentials, not both.
        OAuth credentials take precedence if both are provided.
        """
        self._credentials: Optional[Credentials] = None
        self._service_account_file = service_account_file
        self._service_account_info = service_account_info
        self._oauth_credentials = oauth_credentials
        self._use_oauth = oauth_credentials is not None

    def get_credentials(self) -> Credentials:
        """
        Get valid credentials, loading or refreshing as needed.

        Returns:
            Valid Google credentials
        """
        if self._credentials is None:
            if self._use_oauth:
                self._credentials = get_oauth_credentials_from_dict(self._oauth_credentials)
            else:
                self._credentials = get_service_account_credentials(
                    service_account_file=self._service_account_file,
                    service_account_info=self._service_account_info,
                )

        # Check if credentials need refresh
        if self._credentials.expired:
            if self._use_oauth and self._credentials.refresh_token:
                # OAuth credentials need a Request object for refresh
                import google.auth.transport.requests
                request = google.auth.transport.requests.Request()
                self._credentials.refresh(request)
            else:
                # Service account credentials auto-refresh with None
                self._credentials.refresh(None)

        return self._credentials

    @property
    def is_oauth(self) -> bool:
        """Check if using OAuth credentials."""
        return self._use_oauth

    @property
    def service_account_email(self) -> Optional[str]:
        """Get the service account email for sharing calendars."""
        if self._use_oauth:
            return None
        creds = self.get_credentials()
        if hasattr(creds, "service_account_email"):
            return creds.service_account_email
        return None
