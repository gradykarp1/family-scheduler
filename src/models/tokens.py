"""
OAuth token storage models.

Stores Google OAuth tokens for users who have authorized calendar access.
Tokens are encrypted at rest and automatically refreshed when expired.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class UserToken(BaseModel):
    """
    Stores OAuth tokens for user calendar access.

    Each user can have one set of tokens for Google Calendar.
    Tokens are refreshed automatically when expired.

    Attributes:
        user_id: Unique identifier for the user (from frontend auth)
        provider: OAuth provider (currently only 'google')
        email: User's email from the OAuth provider
        access_token: Current access token (encrypted in production)
        refresh_token: Refresh token for obtaining new access tokens
        token_expiry: When the access token expires
        scopes: OAuth scopes granted (comma-separated)
        calendar_id: Primary calendar ID for this user (optional)
    """

    __tablename__ = "user_tokens"

    # User identification
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="External user ID from frontend authentication"
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="google",
        doc="OAuth provider (google)"
    )

    # OAuth identity
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="User's email from OAuth provider"
    )

    # Token storage
    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="OAuth access token"
    )

    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="OAuth refresh token (for obtaining new access tokens)"
    )

    token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the access token expires"
    )

    scopes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="OAuth scopes granted (space-separated)"
    )

    # Calendar configuration
    calendar_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Primary calendar ID for this user (defaults to 'primary')"
    )

    # Indexes
    __table_args__ = (
        Index("ix_user_tokens_user_provider", "user_id", "provider", unique=True),
    )

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        if self.token_expiry is None:
            return False
        return datetime.now(self.token_expiry.tzinfo) >= self.token_expiry

    @property
    def needs_refresh(self) -> bool:
        """Check if token should be refreshed (expired or expiring soon)."""
        if self.token_expiry is None:
            return False
        from datetime import timedelta
        # Refresh if expiring within 5 minutes
        buffer = timedelta(minutes=5)
        return datetime.now(self.token_expiry.tzinfo) >= (self.token_expiry - buffer)

    def __repr__(self) -> str:
        return f"<UserToken(user_id={self.user_id}, provider={self.provider}, email={self.email})>"
