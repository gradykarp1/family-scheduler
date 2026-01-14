"""
Checkpointing configuration for LangGraph orchestrator.

Provides state persistence for multi-turn conversations and workflow recovery.
- Development: In-memory checkpointing (MemorySaver)
- Production: PostgreSQL checkpointing for persistence across serverless invocations
"""

import logging
from typing import Union

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)

# Module-level checkpointer instance (singleton pattern)
_checkpointer: BaseCheckpointSaver | None = None


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Get checkpointer for state persistence.

    Returns PostgreSQL checkpointer in production (when DATABASE_URL is PostgreSQL),
    otherwise returns in-memory MemorySaver for development.

    The checkpointer enables:
    - Multi-turn conversations (state persisted across requests)
    - Workflow resume (pause and continue later)
    - Debugging (inspect intermediate states)
    - Testing (deterministic execution with same thread_id)

    Returns:
        BaseCheckpointSaver instance (PostgresSaver in production, MemorySaver otherwise)

    Example:
        >>> checkpointer = get_checkpointer()
        >>> graph = graph.compile(checkpointer=checkpointer)
        >>> # Invoke with thread_id for persistence
        >>> result = graph.invoke(state, config={"configurable": {"thread_id": "conv_123"}})
    """
    global _checkpointer

    if _checkpointer is None:
        _checkpointer = _create_checkpointer()

    return _checkpointer


def _create_checkpointer() -> BaseCheckpointSaver:
    """Create the appropriate checkpointer based on configuration."""
    from src.config import get_settings

    settings = get_settings()

    if settings.uses_postgresql:
        return _create_postgres_checkpointer(settings.database_url)
    else:
        logger.info("Using in-memory checkpointer (development mode)")
        return MemorySaver()


def _create_postgres_checkpointer(database_url: str) -> BaseCheckpointSaver:
    """
    Create PostgreSQL checkpointer for production.

    Args:
        database_url: PostgreSQL connection string

    Returns:
        PostgresSaver instance
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        # Create checkpointer with connection pool
        checkpointer = PostgresSaver.from_conn_string(database_url)

        # Ensure checkpoint tables exist
        checkpointer.setup()

        logger.info("Using PostgreSQL checkpointer (production mode)")
        return checkpointer

    except ImportError:
        logger.warning(
            "langgraph-checkpoint-postgres not installed. "
            "Install with: pip install langgraph-checkpoint-postgres"
        )
        logger.warning("Falling back to in-memory checkpointer")
        return MemorySaver()

    except Exception as e:
        logger.error(f"Failed to create PostgreSQL checkpointer: {e}")
        logger.warning("Falling back to in-memory checkpointer")
        return MemorySaver()


def reset_checkpointer() -> None:
    """
    Reset checkpointer (useful for testing).

    Clears all stored state, starting fresh.
    """
    global _checkpointer
    _checkpointer = None
