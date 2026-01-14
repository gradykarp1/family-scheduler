"""
Webhook API routes for event notifications.

Allows external services to register webhooks for receiving
push notifications when calendar events change.
"""

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.models.webhooks import Webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateWebhookRequest(BaseModel):
    """Request to create a new webhook."""

    url: str = Field(
        ...,
        description="HTTPS URL to send notifications to",
        examples=["https://example.com/webhook"],
    )
    event_types: list[str] = Field(
        default=["event.created", "event.updated", "event.deleted"],
        description="Event types to receive",
    )
    description: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional description of webhook purpose",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, v: list[str]) -> list[str]:
        valid_types = {"event.created", "event.updated", "event.deleted"}
        for event_type in v:
            if event_type not in valid_types:
                raise ValueError(
                    f"Invalid event type: {event_type}. "
                    f"Valid types: {', '.join(valid_types)}"
                )
        return v


class WebhookResponse(BaseModel):
    """Response for a webhook."""

    id: str = Field(..., description="Webhook ID")
    url: str = Field(..., description="Webhook URL")
    event_types: list[str] = Field(..., description="Event types subscribed to")
    description: Optional[str] = Field(None, description="Webhook description")
    active: bool = Field(..., description="Whether webhook is active")
    secret: str = Field(..., description="Webhook secret for signature verification")
    created_at: str = Field(..., description="When webhook was created")


class WebhookListResponse(BaseModel):
    """Response for listing webhooks."""

    webhooks: list[WebhookResponse] = Field(..., description="List of webhooks")
    total: int = Field(..., description="Total number of webhooks")


class DeleteWebhookResponse(BaseModel):
    """Response for deleting a webhook."""

    success: bool = Field(..., description="Whether deletion was successful")
    webhook_id: str = Field(..., description="ID of deleted webhook")
    message: str = Field(..., description="Status message")


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_secret() -> str:
    """Generate a random webhook secret."""
    return secrets.token_urlsafe(32)


def _webhook_to_response(webhook: Webhook) -> WebhookResponse:
    """Convert Webhook model to response."""
    return WebhookResponse(
        id=str(webhook.id),
        url=webhook.url,
        event_types=webhook.event_type_list,
        description=webhook.description,
        active=webhook.active,
        secret=webhook.secret,
        created_at=webhook.created_at.isoformat() if webhook.created_at else "",
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    request: CreateWebhookRequest,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    session: AsyncSession = Depends(get_async_session),
) -> WebhookResponse:
    """
    Register a new webhook.

    Creates a webhook that will receive POST requests when calendar
    events are created, updated, or deleted.

    The response includes a `secret` field - save this securely!
    It's used to verify webhook signatures and won't be shown again.

    Webhook payloads are signed with HMAC-SHA256:
    - Header: X-Webhook-Signature
    - Signature: HMAC-SHA256(payload, secret)
    """
    user_id = x_user_id or "default_user"

    # Generate secret for this webhook
    secret = _generate_secret()

    # Create webhook
    webhook = Webhook(
        user_id=user_id,
        url=request.url,
        secret=secret,
        event_types=",".join(request.event_types),
        description=request.description,
        active=True,
    )

    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)

    logger.info(f"Created webhook {webhook.id} for user {user_id}")

    return _webhook_to_response(webhook)


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    x_user_id: Optional[str] = Header(None, description="User ID"),
    session: AsyncSession = Depends(get_async_session),
) -> WebhookListResponse:
    """
    List all webhooks for the current user.

    Note: Secrets are included in the response. In production,
    you may want to redact or omit them.
    """
    user_id = x_user_id or "default_user"

    stmt = select(Webhook).where(
        Webhook.user_id == user_id,
        Webhook.deleted_at.is_(None),
    ).order_by(Webhook.created_at.desc())

    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    return WebhookListResponse(
        webhooks=[_webhook_to_response(w) for w in webhooks],
        total=len(webhooks),
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    session: AsyncSession = Depends(get_async_session),
) -> WebhookResponse:
    """
    Get a specific webhook by ID.
    """
    user_id = x_user_id or "default_user"

    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.user_id == user_id,
        Webhook.deleted_at.is_(None),
    )

    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()

    if webhook is None:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")

    return _webhook_to_response(webhook)


@router.delete("/{webhook_id}", response_model=DeleteWebhookResponse)
async def delete_webhook(
    webhook_id: str,
    x_user_id: Optional[str] = Header(None, description="User ID"),
    session: AsyncSession = Depends(get_async_session),
) -> DeleteWebhookResponse:
    """
    Delete a webhook.

    This is a soft delete - the webhook is deactivated but retained
    for audit purposes.
    """
    user_id = x_user_id or "default_user"

    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.user_id == user_id,
        Webhook.deleted_at.is_(None),
    )

    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()

    if webhook is None:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")

    # Soft delete
    from datetime import datetime, timezone
    webhook.deleted_at = datetime.now(timezone.utc)
    webhook.active = False
    await session.commit()

    logger.info(f"Deleted webhook {webhook_id} for user {user_id}")

    return DeleteWebhookResponse(
        success=True,
        webhook_id=webhook_id,
        message="Webhook deleted successfully",
    )


@router.patch("/{webhook_id}/toggle", response_model=WebhookResponse)
async def toggle_webhook(
    webhook_id: str,
    active: bool = Query(..., description="Set webhook active status"),
    x_user_id: Optional[str] = Header(None, description="User ID"),
    session: AsyncSession = Depends(get_async_session),
) -> WebhookResponse:
    """
    Enable or disable a webhook.
    """
    user_id = x_user_id or "default_user"

    stmt = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.user_id == user_id,
        Webhook.deleted_at.is_(None),
    )

    result = await session.execute(stmt)
    webhook = result.scalar_one_or_none()

    if webhook is None:
        raise HTTPException(status_code=404, detail=f"Webhook {webhook_id} not found")

    webhook.active = active
    if active:
        webhook.failure_count = 0  # Reset failures on re-enable
    await session.commit()

    logger.info(f"Set webhook {webhook_id} active={active}")

    return _webhook_to_response(webhook)
