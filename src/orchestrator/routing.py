"""
Routing logic for LangGraph orchestrator.

Contains decision functions that determine workflow paths based on state.
These functions are used with LangGraph's conditional edges.
"""

from typing import Literal
import logging

from src.agents.state import FamilySchedulerState

logger = logging.getLogger(__name__)

# Confidence threshold for routing decisions
CONFIDENCE_THRESHOLD = 0.7


def route_after_nl_parser(
    state: FamilySchedulerState,
) -> Literal["scheduling", "query", "clarification"]:
    """
    Route after NL Parser based on confidence and intent.

    Routing Logic:
    1. If confidence < 0.7 -> clarification (need more info)
    2. If intent is 'query' -> query agent (answer question)
    3. Otherwise -> scheduling (create/modify event)

    Args:
        state: Current workflow state with NL Parser output

    Returns:
        String key for next node: "scheduling", "query", or "clarification"
    """
    conv_id = state.get("conversation_id", "unknown")

    # Get NL Parser output
    agent_outputs = state.get("agent_outputs", {})
    nl_output = agent_outputs.get("nl_parser", {})

    confidence = nl_output.get("confidence", 0.0)
    parsed_data = nl_output.get("data", {})
    intent = parsed_data.get("event_type", "create")

    # Check confidence threshold
    if confidence < CONFIDENCE_THRESHOLD:
        logger.info(
            f"[{conv_id}] Routing to clarification: "
            f"confidence {confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}"
        )
        return "clarification"

    # Check intent type
    if intent == "query":
        logger.info(f"[{conv_id}] Routing to query agent: query intent detected")
        return "query"

    # Default: event creation/modification
    logger.info(
        f"[{conv_id}] Routing to scheduling: "
        f"intent={intent}, confidence={confidence:.2f}"
    )
    return "scheduling"


def route_after_conflict_detection(
    state: FamilySchedulerState,
) -> Literal["resolution", "auto_confirm"]:
    """
    Route after Conflict Detection based on detected conflicts.

    Routing Logic:
    - Conflicts detected -> resolution agent
    - No conflicts -> auto_confirm

    Args:
        state: Current workflow state with Conflict Detection output

    Returns:
        String key for next node: "resolution" or "auto_confirm"
    """
    conv_id = state.get("conversation_id", "unknown")

    # Get conflict detection results
    detected_conflicts = state.get("detected_conflicts", {})
    has_conflicts = detected_conflicts.get("has_conflicts", False)

    if has_conflicts:
        conflicts = detected_conflicts.get("conflicts", [])
        conflict_count = len(conflicts)
        logger.info(
            f"[{conv_id}] Routing to resolution: {conflict_count} conflicts detected"
        )
        return "resolution"

    logger.info(f"[{conv_id}] Routing to auto_confirm: no conflicts detected")
    return "auto_confirm"


def route_on_error(
    state: FamilySchedulerState,
) -> Literal["continue", "end"]:
    """
    Check if workflow should continue or terminate due to errors.

    Called after nodes that may fail to determine if workflow should continue.

    Args:
        state: Current workflow state

    Returns:
        "continue" to proceed, "end" to terminate
    """
    conv_id = state.get("conversation_id", "unknown")
    workflow_status = state.get("workflow_status", "in_progress")

    if workflow_status == "failed":
        errors = state.get("errors", [])
        error_count = len(errors)
        logger.warning(
            f"[{conv_id}] Workflow failed with {error_count} errors, terminating"
        )
        return "end"

    return "continue"


def route_scheduling_result(
    state: FamilySchedulerState,
) -> Literal["resource_manager", "clarification", "end"]:
    """
    Route after Scheduling based on result.

    Routing Logic:
    - Scheduling successful -> resource_manager
    - No viable time slots -> clarification (ask user for flexibility)
    - Error -> end

    Args:
        state: Current workflow state with Scheduling output

    Returns:
        String key for next node
    """
    conv_id = state.get("conversation_id", "unknown")
    workflow_status = state.get("workflow_status", "in_progress")

    # Check for errors
    if workflow_status == "failed":
        return "end"

    # Get scheduling output
    agent_outputs = state.get("agent_outputs", {})
    scheduling_output = agent_outputs.get("scheduling", {})
    scheduling_data = scheduling_output.get("data", {})
    candidate_times = scheduling_data.get("candidate_times", [])

    if not candidate_times:
        logger.info(
            f"[{conv_id}] Routing to clarification: no viable time slots found"
        )
        return "clarification"

    logger.info(
        f"[{conv_id}] Routing to resource_manager: "
        f"{len(candidate_times)} candidate times found"
    )
    return "resource_manager"


def route_resource_result(
    state: FamilySchedulerState,
) -> Literal["conflict_detection", "clarification", "end"]:
    """
    Route after Resource Manager based on availability.

    Routing Logic:
    - All resources available -> conflict_detection
    - Resources unavailable -> clarification (suggest alternatives)
    - Error -> end

    Args:
        state: Current workflow state with Resource Manager output

    Returns:
        String key for next node
    """
    conv_id = state.get("conversation_id", "unknown")
    workflow_status = state.get("workflow_status", "in_progress")

    # Check for errors
    if workflow_status == "failed":
        return "end"

    # Get resource manager output
    agent_outputs = state.get("agent_outputs", {})
    resource_output = agent_outputs.get("resource_manager", {})
    resource_data = resource_output.get("data", {})
    all_available = resource_data.get("all_resources_available", True)

    if not all_available:
        logger.info(
            f"[{conv_id}] Routing to clarification: some resources unavailable"
        )
        return "clarification"

    logger.info(f"[{conv_id}] Routing to conflict_detection: all resources available")
    return "conflict_detection"
