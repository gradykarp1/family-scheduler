"""
Token storage and retrieval for OAuth tokens.

Provides database persistence for user OAuth tokens with automatic
token refresh when expired.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tokens import UserToken
from src.auth.google_oauth import (
    OAuthTokens,
    refresh_access_token,
    GoogleUserInfo,
)

logger = logging.getLogger(__name__)


async def get_user_token(
    session: AsyncSession,
    user_id: str,
    provider: str = "google"
) -> Optional[UserToken]:
    """
    Get a user's stored OAuth token.

    Args:
        session: Database session
        user_id: The user's ID
        provider: OAuth provider (default: google)

    Returns:
        UserToken if found, None otherwise
    """
    stmt = select(UserToken).where(
        UserToken.user_id == user_id,
        UserToken.provider == provider,
        UserToken.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def save_user_token(
    session: AsyncSession,
    user_id: str,
    tokens: OAuthTokens,
    user_info: GoogleUserInfo,
    provider: str = "google",
) -> UserToken:
    """
    Save or update a user's OAuth tokens.

    If a token already exists for the user/provider, it will be updated.
    Otherwise, a new token record will be created.

    Args:
        session: Database session
        user_id: The user's ID
        tokens: OAuth tokens from authorization
        user_info: User info from OAuth provider
        provider: OAuth provider (default: google)

    Returns:
        The saved UserToken
    """
    # Check for existing token
    existing = await get_user_token(session, user_id, provider)

    if existing:
        # Update existing token
        existing.access_token = tokens.access_token
        if tokens.refresh_token:
            existing.refresh_token = tokens.refresh_token
        existing.token_expiry = tokens.expiry
        existing.scopes = tokens.scope
        existing.email = user_info.email
        existing.updated_at = datetime.now(timezone.utc)

        logger.info(f"Updated OAuth token for user {user_id}")
        await session.commit()
        return existing
    else:
        # Create new token
        user_token = UserToken(
            user_id=user_id,
            provider=provider,
            email=user_info.email,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_expiry=tokens.expiry,
            scopes=tokens.scope,
        )
        session.add(user_token)
        await session.commit()
        await session.refresh(user_token)

        logger.info(f"Created new OAuth token for user {user_id}")
        return user_token


async def delete_user_token(
    session: AsyncSession,
    user_id: str,
    provider: str = "google",
) -> bool:
    """
    Delete a user's OAuth token (soft delete).

    Args:
        session: Database session
        user_id: The user's ID
        provider: OAuth provider (default: google)

    Returns:
        True if token was deleted, False if not found
    """
    token = await get_user_token(session, user_id, provider)
    if token:
        token.deleted_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(f"Deleted OAuth token for user {user_id}")
        return True
    return False


async def get_valid_access_token(
    session: AsyncSession,
    user_id: str,
    provider: str = "google",
) -> Optional[str]:
    """
    Get a valid access token for a user, refreshing if necessary.

    This is the main function to use when you need an access token
    for API calls. It handles token refresh automatically.

    Args:
        session: Database session
        user_id: The user's ID
        provider: OAuth provider (default: google)

    Returns:
        Valid access token, or None if user has no token
    """
    token = await get_user_token(session, user_id, provider)
    if not token:
        return None

    # Check if token needs refresh
    if token.needs_refresh:
        if not token.refresh_token:
            logger.warning(f"Token expired and no refresh token for user {user_id}")
            return None

        try:
            # Refresh the token
            new_tokens = await refresh_access_token(token.refresh_token)

            # Update stored token
            token.access_token = new_tokens.access_token
            token.token_expiry = new_tokens.expiry
            if new_tokens.refresh_token:
                token.refresh_token = new_tokens.refresh_token
            token.updated_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info(f"Refreshed access token for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to refresh token for user {user_id}: {e}")
            return None

    return token.access_token


async def get_user_credentials(
    session: AsyncSession,
    user_id: str,
) -> Optional[dict]:
    """
    Get Google credentials dict for a user's calendar access.

    Returns credentials in a format suitable for Google API clients.

    Args:
        session: Database session
        user_id: The user's ID

    Returns:
        Dict with token, refresh_token, etc., or None if not found
    """
    token = await get_user_token(session, user_id, "google")
    if not token:
        return None

    # Get a valid access token (refreshes if needed)
    access_token = await get_valid_access_token(session, user_id, "google")
    if not access_token:
        return None

    return {
        "token": access_token,
        "refresh_token": token.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": token.scopes.split(" ") if token.scopes else [],
    }
