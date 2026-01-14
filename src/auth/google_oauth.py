"""
Google OAuth 2.0 implementation for calendar access.

Implements the OAuth 2.0 authorization code flow:
1. Generate authorization URL → user redirected to Google
2. User grants permission → Google redirects back with code
3. Exchange code for tokens → access_token + refresh_token
4. Use access_token to call Calendar API
5. Refresh access_token when expired using refresh_token
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Calendar API scopes
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
]


@dataclass
class OAuthTokens:
    """OAuth token response from Google."""

    access_token: str
    refresh_token: Optional[str]
    expires_in: int
    token_type: str
    scope: str

    @property
    def expiry(self) -> datetime:
        """Calculate token expiry time."""
        return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)


@dataclass
class GoogleUserInfo:
    """User info from Google OAuth."""

    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class GoogleOAuthFlow:
    """
    Manages the Google OAuth 2.0 flow.

    Usage:
        flow = GoogleOAuthFlow()

        # Step 1: Get authorization URL
        auth_url = flow.get_authorization_url(state="random_state")
        # Redirect user to auth_url

        # Step 2: Handle callback with authorization code
        tokens = await flow.exchange_code(code)

        # Step 3: Get user info
        user_info = await flow.get_user_info(tokens.access_token)

        # Step 4: Refresh token when expired
        new_tokens = await flow.refresh_token(tokens.refresh_token)
    """

    def __init__(self):
        settings = get_settings()
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri

        if not self.client_id or not self.client_secret:
            logger.warning(
                "Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and "
                "GOOGLE_OAUTH_CLIENT_SECRET in environment."
            )

    def get_authorization_url(self, state: str) -> str:
        """
        Generate the Google OAuth authorization URL.

        Args:
            state: Random string to prevent CSRF attacks

        Returns:
            URL to redirect user to for authorization
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(CALENDAR_SCOPES),
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Always show consent screen (ensures refresh token)
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            OAuthTokens with access_token and refresh_token

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()

        logger.info("Successfully exchanged authorization code for tokens")

        return OAuthTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data["expires_in"],
            token_type=token_data["token_type"],
            scope=token_data["scope"],
        )

    async def refresh_token(self, refresh_token: str) -> OAuthTokens:
        """
        Refresh an expired access token.

        Args:
            refresh_token: The refresh token from initial authorization

        Returns:
            New OAuthTokens with fresh access_token

        Raises:
            httpx.HTTPStatusError: If refresh fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=data)
            response.raise_for_status()
            token_data = response.json()

        logger.info("Successfully refreshed access token")

        return OAuthTokens(
            access_token=token_data["access_token"],
            refresh_token=refresh_token,  # Keep original refresh token
            expires_in=token_data["expires_in"],
            token_type=token_data["token_type"],
            scope=token_data.get("scope", ""),
        )

    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """
        Get user info from Google using access token.

        Args:
            access_token: Valid OAuth access token

        Returns:
            GoogleUserInfo with user's email and profile

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
            response.raise_for_status()
            user_data = response.json()

        return GoogleUserInfo(
            email=user_data["email"],
            name=user_data.get("name"),
            picture=user_data.get("picture"),
        )


# Module-level convenience functions
_flow: Optional[GoogleOAuthFlow] = None


def _get_flow() -> GoogleOAuthFlow:
    """Get or create the OAuth flow singleton."""
    global _flow
    if _flow is None:
        _flow = GoogleOAuthFlow()
    return _flow


def get_authorization_url(state: str) -> str:
    """Generate authorization URL. See GoogleOAuthFlow.get_authorization_url."""
    return _get_flow().get_authorization_url(state)


async def exchange_code_for_tokens(code: str) -> OAuthTokens:
    """Exchange code for tokens. See GoogleOAuthFlow.exchange_code."""
    return await _get_flow().exchange_code(code)


async def refresh_access_token(refresh_token: str) -> OAuthTokens:
    """Refresh access token. See GoogleOAuthFlow.refresh_token."""
    return await _get_flow().refresh_token(refresh_token)


async def get_google_user_info(access_token: str) -> GoogleUserInfo:
    """Get user info. See GoogleOAuthFlow.get_user_info."""
    return await _get_flow().get_user_info(access_token)
