"""
LangGraph Orchestrator for Family Scheduler.

This module provides the central orchestration layer that coordinates all
specialized agents through a LangGraph StateGraph. It implements ADR-015.

The orchestrator:
- Routes user requests through specialized agents in correct order
- Supports conditional branching based on agent outputs
- Handles low-confidence scenarios requiring clarification
- Manages conflict resolution workflow
- Maintains conversation context for multi-turn interactions
- Logs all agent invocations for audit trail

Usage:
    from src.orchestrator import build_orchestrator_graph, invoke_orchestrator

    # Build graph once at startup
    graph = build_orchestrator_graph()

    # Invoke for each request
    result = invoke_orchestrator(
        graph,
        user_input="Schedule soccer practice Saturday at 2pm",
        user_id="user_123",
        conversation_id="conv_456"
    )
"""

from typing import Any
from datetime import datetime, timezone
import uuid
import logging

from langgraph.graph import StateGraph, END

from src.agents.state import FamilySchedulerState
from src.orchestrator.checkpointing import get_checkpointer
from src.orchestrator.nodes import (
    nl_parser_node,
    scheduling_node,
    resource_manager_node,
    conflict_detection_node,
    resolution_node,
    query_node,
    auto_confirm_node,
    request_clarification_node,
)
from src.orchestrator.routing import (
    route_after_nl_parser,
    route_after_conflict_detection,
    route_scheduling_result,
    route_resource_result,
)

logger = logging.getLogger(__name__)

# Module-level compiled graph (singleton)
_compiled_graph = None


def build_orchestrator_graph() -> StateGraph:
    """
    Build the LangGraph orchestrator for Family Scheduler.

    This function constructs the workflow graph with:
    - 8 specialized nodes (agents)
    - Conditional routing based on confidence and conflicts
    - In-memory checkpointing for state persistence

    Returns:
        Compiled StateGraph ready for invocation

    Example:
        >>> graph = build_orchestrator_graph()
        >>> result = graph.invoke(initial_state, config={"configurable": {"thread_id": "conv_123"}})

    Graph Structure:
        NL Parser -> [routing decision]
            -> Scheduling -> Resource Manager -> Conflict Detection -> [routing decision]
                -> Resolution (if conflicts) -> END
                -> Auto Confirm (if no conflicts) -> END
            -> Query -> END
            -> Clarification -> END
    """
    logger.info("Building orchestrator graph")

    # Initialize graph with state schema
    graph = StateGraph(FamilySchedulerState)

    # Add nodes (agent invocations)
    graph.add_node("nl_parser", nl_parser_node)
    graph.add_node("scheduling", scheduling_node)
    graph.add_node("resource_manager", resource_manager_node)
    graph.add_node("conflict_detection", conflict_detection_node)
    graph.add_node("resolution", resolution_node)
    graph.add_node("query", query_node)
    graph.add_node("auto_confirm", auto_confirm_node)
    graph.add_node("request_clarification", request_clarification_node)

    # Set entry point
    graph.set_entry_point("nl_parser")

    # Add conditional edges after NL Parser
    # Routes to: scheduling, query, or clarification
    graph.add_conditional_edges(
        "nl_parser",
        route_after_nl_parser,
        {
            "scheduling": "scheduling",
            "query": "query",
            "clarification": "request_clarification",
        },
    )

    # Add conditional edges after Scheduling
    # Routes to: resource_manager, clarification, or end
    graph.add_conditional_edges(
        "scheduling",
        route_scheduling_result,
        {
            "resource_manager": "resource_manager",
            "clarification": "request_clarification",
            "end": END,
        },
    )

    # Add conditional edges after Resource Manager
    # Routes to: conflict_detection, clarification, or end
    graph.add_conditional_edges(
        "resource_manager",
        route_resource_result,
        {
            "conflict_detection": "conflict_detection",
            "clarification": "request_clarification",
            "end": END,
        },
    )

    # Add conditional edges after Conflict Detection
    # Routes to: resolution or auto_confirm
    graph.add_conditional_edges(
        "conflict_detection",
        route_after_conflict_detection,
        {
            "resolution": "resolution",
            "auto_confirm": "auto_confirm",
        },
    )

    # Terminal edges
    graph.add_edge("resolution", END)
    graph.add_edge("auto_confirm", END)
    graph.add_edge("query", END)
    graph.add_edge("request_clarification", END)

    # Compile graph with checkpointer
    checkpointer = get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)

    logger.info("Orchestrator graph built successfully")
    return compiled


def get_orchestrator_graph() -> StateGraph:
    """
    Get or create the singleton orchestrator graph.

    The graph is compiled once and reused for all requests.
    This provides better performance than rebuilding per-request.

    Returns:
        Compiled StateGraph instance
    """
    global _compiled_graph

    if _compiled_graph is None:
        _compiled_graph = build_orchestrator_graph()

    return _compiled_graph


def initialize_state(
    user_input: str,
    user_id: str,
    conversation_id: str | None = None,
) -> FamilySchedulerState:
    """
    Initialize workflow state for a new request.

    Args:
        user_input: Natural language request from user
        user_id: ID of family member making request
        conversation_id: Optional conversation ID (generated if not provided)

    Returns:
        Initialized FamilySchedulerState ready for graph invocation
    """
    now = datetime.now(timezone.utc).isoformat()

    return FamilySchedulerState(
        user_input=user_input,
        user_id=user_id,
        conversation_id=conversation_id or str(uuid.uuid4()),
        current_step="start",
        workflow_status="in_progress",
        messages=[],
        agent_outputs={},
        validation_results=[],
        errors=[],
        retry_count=0,
        created_at=now,
        updated_at=now,
        audit_log=[],
    )


def invoke_orchestrator(
    graph: StateGraph,
    user_input: str,
    user_id: str,
    conversation_id: str | None = None,
) -> FamilySchedulerState:
    """
    Invoke the orchestrator graph with a user request.

    This is the main entry point for processing scheduling requests.

    Args:
        graph: Compiled orchestrator graph
        user_input: Natural language request from user
        user_id: ID of family member making request
        conversation_id: Optional conversation ID for multi-turn conversations

    Returns:
        Final workflow state with agent outputs and results

    Example:
        >>> graph = get_orchestrator_graph()
        >>> result = invoke_orchestrator(
        ...     graph,
        ...     user_input="Schedule dentist appointment Tuesday at 3pm",
        ...     user_id="user_123"
        ... )
        >>> print(result["workflow_status"])
        'completed'
        >>> print(result["proposed_event"])
        {'title': 'dentist appointment', ...}
    """
    # Initialize state
    initial_state = initialize_state(
        user_input=user_input,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    conv_id = initial_state["conversation_id"]
    logger.info(f"[{conv_id}] Invoking orchestrator: '{user_input[:50]}...'")

    # Invoke graph with thread_id for checkpointing
    config = {"configurable": {"thread_id": conv_id}}

    try:
        final_state = graph.invoke(initial_state, config=config)

        logger.info(
            f"[{conv_id}] Orchestrator completed: "
            f"status={final_state.get('workflow_status')}"
        )

        return final_state

    except Exception as e:
        logger.error(f"[{conv_id}] Orchestrator invocation failed: {e}", exc_info=True)

        # Return error state
        return FamilySchedulerState(
            **initial_state,
            workflow_status="failed",
            errors=[
                {
                    "error_type": "orchestrator_failure",
                    "agent": "orchestrator",
                    "message": f"Workflow execution failed: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "retryable": True,
                }
            ],
        )


def analyze_result(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Analyze final workflow state and determine result type.

    Useful for API response formatting.

    Args:
        state: Final workflow state

    Returns:
        Dictionary with result analysis:
        - result_type: "completed", "awaiting_user", "error"
        - message: Human-readable summary
        - data: Relevant data based on result type
    """
    workflow_status = state.get("workflow_status", "unknown")

    if workflow_status == "failed":
        errors = state.get("errors", [])
        return {
            "result_type": "error",
            "message": errors[-1].get("message", "An error occurred") if errors else "Unknown error",
            "data": {"errors": errors},
        }

    if workflow_status == "awaiting_user":
        # Check what we're waiting for
        detected_conflicts = state.get("detected_conflicts", {})

        if detected_conflicts.get("has_conflicts"):
            resolution_output = state.get("agent_outputs", {}).get("resolution", {})
            return {
                "result_type": "awaiting_resolution",
                "message": "Conflicts detected. Please select a resolution option.",
                "data": {
                    "conflicts": detected_conflicts.get("conflicts", []),
                    "resolutions": resolution_output.get("data", {}).get("proposed_resolutions", []),
                },
            }

        clarification_output = state.get("agent_outputs", {}).get("clarification", {})
        return {
            "result_type": "awaiting_clarification",
            "message": clarification_output.get("data", {}).get("message", "Please provide more details."),
            "data": {
                "missing_fields": clarification_output.get("data", {}).get("missing_fields", []),
            },
        }

    if workflow_status == "completed":
        # Check what completed
        proposed_event = state.get("proposed_event")
        query_output = state.get("agent_outputs", {}).get("query")

        if proposed_event:
            return {
                "result_type": "event_created",
                "message": f"Event '{proposed_event.get('title')}' has been scheduled.",
                "data": {"event": proposed_event},
            }

        if query_output:
            return {
                "result_type": "query_answered",
                "message": query_output.get("data", {}).get("results", {}).get("response", ""),
                "data": {"query_result": query_output.get("data")},
            }

    return {
        "result_type": "unknown",
        "message": "Workflow completed with unknown result",
        "data": {},
    }


# Public API
__all__ = [
    "build_orchestrator_graph",
    "get_orchestrator_graph",
    "initialize_state",
    "invoke_orchestrator",
    "analyze_result",
]
