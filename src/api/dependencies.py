"""
FastAPI dependency injection providers.

Provides orchestrator, database sessions, and user context.
"""

from typing import Optional
import logging

from fastapi import Depends, Header, HTTPException

from src.orchestrator import get_orchestrator_graph
from src.database import get_db

logger = logging.getLogger(__name__)

# Global orchestrator instance (initialized at startup)
_orchestrator = None


def init_orchestrator():
    """Initialize orchestrator at application startup."""
    global _orchestrator
    _orchestrator = get_orchestrator_graph()
    logger.info("Orchestrator initialized")


def get_orchestrator():
    """
    Dependency injection for orchestrator.

    Returns the singleton orchestrator graph instance.

    Raises:
        HTTPException: If orchestrator not initialized
    """
    if _orchestrator is None:
        logger.error("Orchestrator not initialized")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable - orchestrator not initialized",
        )
    return _orchestrator


def get_db_session():
    """
    Dependency injection for database session.

    Yields a database session and ensures cleanup.
    """
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


def get_user_context(
    x_user_id: Optional[str] = Header(None, description="User ID"),
    x_family_id: Optional[str] = Header(None, description="Family ID"),
) -> dict:
    """
    Extract user context from headers.

    Priority: Header value > default

    Args:
        x_user_id: User ID from X-User-ID header
        x_family_id: Family ID from X-Family-ID header

    Returns:
        Dictionary with user_id and family_id
    """
    return {
        "user_id": x_user_id or "default_user",
        "family_id": x_family_id or "default_family",
    }


def resolve_user_id(
    request_user_id: Optional[str],
    header_user_id: Optional[str],
) -> str:
    """
    Resolve user ID from request body or header.

    Priority: request body > header > default

    Args:
        request_user_id: User ID from request body
        header_user_id: User ID from header

    Returns:
        Resolved user ID
    """
    return request_user_id or header_user_id or "default_user"
