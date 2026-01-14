"""
Webhook delivery service.

Handles sending webhook notifications to registered endpoints
with HMAC signature verification and retry logic.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.webhooks import Webhook

logger = logging.getLogger(__name__)

# Delivery configuration
WEBHOOK_TIMEOUT = 10.0  # seconds
MAX_RETRIES = 3
RETRY_DELAYS = [1, 5, 30]  # seconds between retries


def generate_signature(payload: str, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: JSON string payload
        secret: Webhook secret

    Returns:
        Hex-encoded signature
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def deliver_webhook(
    webhook: Webhook,
    event_type: str,
    payload: dict[str, Any],
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Deliver a webhook notification.

    Args:
        webhook: Webhook to deliver to
        event_type: Type of event (e.g., "event.created")
        payload: Event payload data
        session: Optional database session for updating webhook status

    Returns:
        True if delivery succeeded, False otherwise
    """
    if not webhook.should_trigger(event_type):
        logger.debug(f"Webhook {webhook.id} not configured for {event_type}")
        return True  # Not a failure, just not subscribed

    # Build webhook payload
    webhook_payload = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    payload_json = json.dumps(webhook_payload, default=str)

    # Generate signature
    signature = generate_signature(payload_json, webhook.secret)

    # Headers
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event_type,
        "X-Webhook-Timestamp": webhook_payload["timestamp"],
    }

    # Attempt delivery with retries
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                response = await client.post(
                    webhook.url,
                    content=payload_json,
                    headers=headers,
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        f"Webhook {webhook.id} delivered successfully "
                        f"(status {response.status_code})"
                    )
                    if session:
                        webhook.record_success()
                        await session.commit()
                    return True

                # Non-2xx response
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    f"Webhook {webhook.id} delivery failed (attempt {attempt + 1}): "
                    f"{last_error}"
                )

        except httpx.TimeoutException:
            last_error = "Request timed out"
            logger.warning(
                f"Webhook {webhook.id} timed out (attempt {attempt + 1})"
            )
        except httpx.RequestError as e:
            last_error = str(e)
            logger.warning(
                f"Webhook {webhook.id} request error (attempt {attempt + 1}): {e}"
            )
        except Exception as e:
            last_error = str(e)
            logger.error(
                f"Webhook {webhook.id} unexpected error (attempt {attempt + 1}): {e}"
            )

        # Wait before retry (unless this was the last attempt)
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_DELAYS[attempt]
            await asyncio.sleep(delay)

    # All retries failed
    logger.error(
        f"Webhook {webhook.id} delivery failed after {MAX_RETRIES} attempts: {last_error}"
    )
    if session:
        webhook.record_failure()
        await session.commit()

    return False


async def trigger_webhooks(
    user_id: str,
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession,
) -> dict[str, bool]:
    """
    Trigger all active webhooks for a user.

    Args:
        user_id: User whose webhooks to trigger
        event_type: Type of event
        payload: Event payload data
        session: Database session

    Returns:
        Dict mapping webhook_id to delivery success
    """
    # Get all active webhooks for the user
    stmt = select(Webhook).where(
        Webhook.user_id == user_id,
        Webhook.active == True,
        Webhook.deleted_at.is_(None),
    )

    result = await session.execute(stmt)
    webhooks = result.scalars().all()

    if not webhooks:
        logger.debug(f"No active webhooks for user {user_id}")
        return {}

    logger.info(
        f"Triggering {len(webhooks)} webhooks for user {user_id} "
        f"(event: {event_type})"
    )

    # Deliver to all webhooks concurrently
    results = {}
    tasks = []

    for webhook in webhooks:
        if webhook.should_trigger(event_type):
            tasks.append((webhook, deliver_webhook(webhook, event_type, payload, session)))

    # Execute all deliveries concurrently
    for webhook, task in tasks:
        try:
            success = await task
            results[str(webhook.id)] = success
        except Exception as e:
            logger.error(f"Error delivering webhook {webhook.id}: {e}")
            results[str(webhook.id)] = False

    return results


async def trigger_event_created(
    user_id: str,
    event_data: dict[str, Any],
    session: AsyncSession,
) -> dict[str, bool]:
    """
    Trigger webhooks for event.created.

    Args:
        user_id: User who created the event
        event_data: Event data to send
        session: Database session

    Returns:
        Dict mapping webhook_id to delivery success
    """
    return await trigger_webhooks(user_id, "event.created", event_data, session)


async def trigger_event_updated(
    user_id: str,
    event_data: dict[str, Any],
    session: AsyncSession,
) -> dict[str, bool]:
    """
    Trigger webhooks for event.updated.

    Args:
        user_id: User who updated the event
        event_data: Event data to send
        session: Database session

    Returns:
        Dict mapping webhook_id to delivery success
    """
    return await trigger_webhooks(user_id, "event.updated", event_data, session)


async def trigger_event_deleted(
    user_id: str,
    event_id: str,
    session: AsyncSession,
) -> dict[str, bool]:
    """
    Trigger webhooks for event.deleted.

    Args:
        user_id: User who deleted the event
        event_id: ID of deleted event
        session: Database session

    Returns:
        Dict mapping webhook_id to delivery success
    """
    return await trigger_webhooks(
        user_id,
        "event.deleted",
        {"event_id": event_id},
        session,
    )
