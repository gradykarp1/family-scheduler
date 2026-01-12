"""
Checkpointing configuration for LangGraph orchestrator.

Provides state persistence for multi-turn conversations and workflow recovery.
Phase 1 uses in-memory checkpointing; Phase 2 will migrate to PostgreSQL.
"""

from langgraph.checkpoint.memory import MemorySaver

# Module-level checkpointer instance (singleton pattern)
_checkpointer: MemorySaver | None = None


def get_checkpointer() -> MemorySaver:
    """
    Get checkpointer for state persistence.

    Phase 1: In-memory (MemorySaver)
    Phase 2: PostgreSQL via custom implementation

    The checkpointer enables:
    - Multi-turn conversations (state persisted across requests)
    - Workflow resume (pause and continue later)
    - Debugging (inspect intermediate states)
    - Testing (deterministic execution with same thread_id)

    Returns:
        MemorySaver instance for in-memory checkpointing

    Example:
        >>> checkpointer = get_checkpointer()
        >>> graph = graph.compile(checkpointer=checkpointer)
        >>> # Invoke with thread_id for persistence
        >>> result = graph.invoke(state, config={"configurable": {"thread_id": "conv_123"}})
    """
    global _checkpointer

    if _checkpointer is None:
        _checkpointer = MemorySaver()

    return _checkpointer


def reset_checkpointer() -> None:
    """
    Reset checkpointer (useful for testing).

    Clears all stored state, starting fresh.
    """
    global _checkpointer
    _checkpointer = None
