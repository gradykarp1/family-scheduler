"""
Webhook registration models.

Stores webhook URLs for receiving notifications when events are
created, updated, or deleted.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel


class Webhook(BaseModel):
    """
    Stores webhook registrations for event notifications.

    Webhooks allow external services (messaging bots, mobile apps, etc.)
    to receive push notifications when calendar events change.

    Attributes:
        user_id: User who owns this webhook
        url: HTTPS URL to send notifications to
        secret: Shared secret for HMAC signature verification
        event_types: Comma-separated list of event types to receive
        description: Optional description of webhook purpose
        active: Whether webhook is currently active
        last_triggered: When webhook was last successfully triggered
        failure_count: Consecutive failures (reset on success)
    """

    __tablename__ = "webhooks"

    # Owner
    user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="User ID who owns this webhook"
    )

    # Webhook configuration
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="HTTPS URL to send notifications to"
    )

    secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Shared secret for HMAC-SHA256 signature"
    )

    event_types: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="event.created,event.updated,event.deleted",
        doc="Comma-separated event types: event.created, event.updated, event.deleted"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Optional description of webhook purpose"
    )

    # Status
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether webhook is active"
    )

    last_triggered: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When webhook was last successfully triggered"
    )

    failure_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        doc="Consecutive delivery failures (resets on success)"
    )

    # Indexes
    __table_args__ = (
        Index("ix_webhooks_user_active", "user_id", "active"),
    )

    @property
    def event_type_list(self) -> list[str]:
        """Get event types as a list."""
        return [t.strip() for t in self.event_types.split(",") if t.strip()]

    def should_trigger(self, event_type: str) -> bool:
        """Check if this webhook should be triggered for an event type."""
        return self.active and event_type in self.event_type_list

    def record_success(self) -> None:
        """Record a successful webhook delivery."""
        from datetime import timezone
        self.last_triggered = datetime.now(timezone.utc)
        self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed webhook delivery."""
        self.failure_count += 1
        # Disable after 10 consecutive failures
        if self.failure_count >= 10:
            self.active = False

    def __repr__(self) -> str:
        return f"<Webhook(user_id={self.user_id}, url={self.url[:50]}..., active={self.active})>"
