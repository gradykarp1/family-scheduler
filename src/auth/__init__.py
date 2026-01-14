"""
Authentication module for Family Scheduler.

Provides OAuth 2.0 authentication for Google Calendar access.
Users authorize the app to access their own calendar.
"""

from src.auth.google_oauth import (
    GoogleOAuthFlow,
    OAuthTokens,
    GoogleUserInfo,
    get_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_google_user_info,
)
from src.auth.token_storage import (
    get_user_token,
    save_user_token,
    delete_user_token,
    get_user_credentials,
    get_valid_access_token,
)

__all__ = [
    # OAuth flow
    "GoogleOAuthFlow",
    "OAuthTokens",
    "GoogleUserInfo",
    "get_authorization_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "get_google_user_info",
    # Token storage
    "get_user_token",
    "save_user_token",
    "delete_user_token",
    "get_user_credentials",
    "get_valid_access_token",
]
