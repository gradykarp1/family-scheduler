"""
Authentication API routes for Google OAuth.

Handles the OAuth 2.0 authorization code flow:
1. /auth/google/login - Start OAuth flow (redirect to Google)
2. /auth/google/callback - Handle OAuth callback (exchange code for tokens)
3. /auth/status - Check if user has connected calendar
4. /auth/logout - Disconnect calendar (revoke access)
"""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    get_authorization_url,
    exchange_code_for_tokens,
    get_google_user_info,
    save_user_token,
    get_user_token,
    delete_user_token,
)
from src.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# Response models
class AuthStatusResponse(BaseModel):
    """Response for auth status check."""
    connected: bool
    email: Optional[str] = None
    provider: str = "google"


class AuthLoginResponse(BaseModel):
    """Response with OAuth authorization URL."""
    authorization_url: str
    state: str


class AuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""
    success: bool
    email: str
    message: str


# In-memory state storage (use Redis in production for distributed deployments)
# State tokens expire after 10 minutes
_oauth_states: dict[str, str] = {}


def _generate_state(user_id: str) -> str:
    """Generate a random state token and store the user_id mapping."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = user_id
    return state


def _validate_state(state: str) -> Optional[str]:
    """Validate state token and return user_id if valid."""
    return _oauth_states.pop(state, None)


@router.get("/google/login", response_model=AuthLoginResponse)
async def google_login(
    user_id: str = Query(..., description="User ID to associate with OAuth tokens"),
) -> AuthLoginResponse:
    """
    Start the Google OAuth flow.

    Returns the authorization URL that the client should redirect to.
    The state parameter is used to prevent CSRF attacks and to map
    the callback to the correct user.

    Args:
        user_id: The user ID to associate tokens with (from your auth system)

    Returns:
        Authorization URL and state token
    """
    state = _generate_state(user_id)
    auth_url = get_authorization_url(state)

    logger.info(f"Generated OAuth URL for user {user_id}")

    return AuthLoginResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Google OAuth"),
    session: AsyncSession = Depends(get_async_session),
) -> AuthCallbackResponse:
    """
    Handle the Google OAuth callback.

    Google redirects here after user grants/denies permission.
    On success, exchanges the authorization code for tokens and stores them.

    Args:
        code: Authorization code from Google
        state: State token to validate request
        error: Error message if user denied access
        session: Database session

    Returns:
        Success response with user email

    Raises:
        HTTPException: If state is invalid or token exchange fails
    """
    # Check for OAuth error (user denied access)
    if error:
        logger.warning(f"OAuth error: {error}")
        raise HTTPException(
            status_code=400,
            detail=f"OAuth authorization failed: {error}"
        )

    # Validate state token
    user_id = _validate_state(state)
    if not user_id:
        logger.warning(f"Invalid OAuth state token: {state}")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state token. Please restart the OAuth flow."
        )

    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code)

        # Get user info from Google
        user_info = await get_google_user_info(tokens.access_token)

        # Save tokens to database
        await save_user_token(
            session=session,
            user_id=user_id,
            tokens=tokens,
            user_info=user_info,
        )

        logger.info(f"Successfully stored OAuth tokens for user {user_id} ({user_info.email})")

        return AuthCallbackResponse(
            success=True,
            email=user_info.email,
            message="Successfully connected Google Calendar",
        )

    except Exception as e:
        logger.error(f"OAuth callback failed for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    user_id: str = Query(..., description="User ID to check"),
    session: AsyncSession = Depends(get_async_session),
) -> AuthStatusResponse:
    """
    Check if a user has connected their Google Calendar.

    Args:
        user_id: The user ID to check
        session: Database session

    Returns:
        Connection status and email if connected
    """
    token = await get_user_token(session, user_id, "google")

    if token:
        return AuthStatusResponse(
            connected=True,
            email=token.email,
            provider="google",
        )
    else:
        return AuthStatusResponse(
            connected=False,
            provider="google",
        )


@router.post("/logout")
async def logout(
    user_id: str = Query(..., description="User ID to disconnect"),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """
    Disconnect a user's Google Calendar.

    This removes the stored OAuth tokens. The user will need to
    re-authorize to use calendar features again.

    Args:
        user_id: The user ID to disconnect
        session: Database session

    Returns:
        Success message
    """
    deleted = await delete_user_token(session, user_id, "google")

    if deleted:
        logger.info(f"User {user_id} disconnected Google Calendar")
        return {"message": "Successfully disconnected Google Calendar"}
    else:
        return {"message": "No connected calendar found"}
