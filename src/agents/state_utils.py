"""
State management utilities for LangGraph workflows.

This module provides helper functions for working with FamilySchedulerState,
including initialization, updates, validation, and optimization.

Implements patterns defined in ADR-012: LangGraph State Schema Design.
"""

from datetime import datetime
from typing import Optional
import uuid

from src.agents.state import (
    FamilySchedulerState,
    AgentOutput,
)


def initialize_state(user_input: str, user_id: str) -> FamilySchedulerState:
    """
    Create fresh state for new workflow.

    Args:
        user_input: Natural language request from user
        user_id: ID of family member making the request

    Returns:
        Initialized state ready for workflow execution

    Example:
        >>> state = initialize_state(
        ...     user_input="Schedule soccer practice Saturday at 2pm",
        ...     user_id="user_123"
        ... )
        >>> state["current_step"]
        'start'
        >>> state["workflow_status"]
        'in_progress'
    """
    conversation_id = f"conv_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.utcnow().isoformat()

    return FamilySchedulerState(
        user_input=user_input,
        user_id=user_id,
        conversation_id=conversation_id,
        current_step="start",
        workflow_status="in_progress",
        next_action="nl_parser",
        messages=[],
        agent_outputs={},
        validation_results=[],
        errors=[],
        retry_count=0,
        created_at=timestamp,
        updated_at=timestamp,
        audit_log=[],
    )


def update_state_with_agent_output(
    state: FamilySchedulerState, agent_name: str, output: AgentOutput
) -> FamilySchedulerState:
    """
    Standard pattern for agents to update state.

    Converts Pydantic AgentOutput model to dict and stores in agent's
    namespace. Updates metadata and audit log.

    Args:
        state: Current state
        agent_name: Name of agent (e.g., "nl_parser", "scheduling")
        output: Agent's output conforming to AgentOutput model

    Returns:
        Updated state

    Example:
        >>> from src.agents.state import AgentOutput
        >>> from datetime import datetime
        >>>
        >>> output = AgentOutput(
        ...     data={"event_type": "create", "title": "Soccer practice"},
        ...     explanation="Parsed as new event creation",
        ...     confidence=0.95,
        ...     reasoning="Clear time reference and event type",
        ...     timestamp=datetime.utcnow().isoformat()
        ... )
        >>> state = update_state_with_agent_output(state, "nl_parser", output)
        >>> state["agent_outputs"]["nl_parser"]["confidence"]
        0.95
    """
    # Convert Pydantic model to dict for TypedDict compatibility
    state["agent_outputs"][agent_name] = output.model_dump()
    state["updated_at"] = datetime.utcnow().isoformat()

    # Add to audit log
    state["audit_log"].append(
        {
            "step": agent_name,
            "timestamp": output.timestamp,
            "confidence": output.confidence,
            "explanation": output.explanation,
        }
    )

    return state


def transition_workflow_step(
    state: FamilySchedulerState, from_step: str, to_step: str
) -> FamilySchedulerState:
    """
    Transition workflow from one step to another.

    Updates current_step, records transition in audit log, and updates
    timestamp.

    Args:
        state: Current state
        from_step: Current step name
        to_step: Next step name

    Returns:
        Updated state

    Example:
        >>> state = transition_workflow_step(
        ...     state,
        ...     from_step="nl_parsing",
        ...     to_step="scheduling"
        ... )
        >>> state["current_step"]
        'scheduling'
    """
    state["current_step"] = to_step
    state["updated_at"] = datetime.utcnow().isoformat()

    state["audit_log"].append(
        {
            "action": "transition",
            "from": from_step,
            "to": to_step,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    return state


def validate_state_transition(
    state: FamilySchedulerState, next_step: str
) -> tuple[bool, Optional[str]]:
    """
    Validate state before transition to next step.

    Checks that required agent outputs exist and meet confidence thresholds
    before allowing transition.

    Args:
        state: Current state
        next_step: Proposed next step

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if transition is valid
        - error_message: None if valid, error description if invalid

    Example:
        >>> valid, error = validate_state_transition(state, "scheduling")
        >>> if not valid:
        ...     print(f"Cannot transition: {error}")
    """
    # Check required fields for next step
    if next_step == "scheduling":
        if "nl_parser" not in state.get("agent_outputs", {}):
            return False, "NL Parser output required for scheduling"

        nl_output = state["agent_outputs"]["nl_parser"]
        if nl_output["confidence"] < 0.5:
            return (
                False,
                f"NL Parser confidence too low: {nl_output['confidence']}",
            )

    elif next_step == "conflict_detection":
        required_agents = ["nl_parser", "scheduling", "resource_manager"]
        missing = [
            a for a in required_agents if a not in state.get("agent_outputs", {})
        ]
        if missing:
            return False, f"Missing required agents: {missing}"

    elif next_step == "resolution":
        if "conflict_detection" not in state.get("agent_outputs", {}):
            return False, "Conflict Detection output required for resolution"

        conflicts = state.get("detected_conflicts")
        if not conflicts or not conflicts.get("has_conflicts"):
            return False, "No conflicts detected, resolution not needed"

    return True, None


def prune_state(state: FamilySchedulerState, keep_messages: int = 10) -> FamilySchedulerState:
    """
    Remove old/unnecessary data from state to manage size.

    Prunes:
    - Old conversation messages (keeps most recent N)
    - Large agent output data after extraction to convenience fields

    Args:
        state: Current state
        keep_messages: Number of recent messages to keep (default: 10)

    Returns:
        Pruned state

    Example:
        >>> state = prune_state(state, keep_messages=10)
        >>> len(state["messages"]) <= 10
        True
    """
    # Keep only last N messages
    if len(state.get("messages", [])) > keep_messages:
        state["messages"] = state["messages"][-keep_messages:]

    # Clear full data after extraction to convenience fields
    if state.get("parsed_event_data"):
        # Data is in convenience field, can clear from agent output
        if "nl_parser" in state.get("agent_outputs", {}):
            agent_out = state["agent_outputs"]["nl_parser"]
            # Keep metadata, clear large data
            state["agent_outputs"]["nl_parser"] = {
                "data": {},  # Cleared
                "explanation": agent_out["explanation"],
                "confidence": agent_out["confidence"],
                "reasoning": agent_out["reasoning"],
                "timestamp": agent_out["timestamp"],
            }

    # Clear scheduling candidates after selection
    if state.get("selected_time_slot"):
        if "scheduling" in state.get("agent_outputs", {}):
            agent_out = state["agent_outputs"]["scheduling"]
            # Keep only selected time, clear all candidates
            state["agent_outputs"]["scheduling"] = {
                "data": {"candidate_times": []},  # Cleared candidates
                "explanation": agent_out["explanation"],
                "confidence": agent_out["confidence"],
                "reasoning": agent_out["reasoning"],
                "timestamp": agent_out["timestamp"],
            }

    return state


def get_agent_output(
    state: FamilySchedulerState, agent_name: str
) -> Optional[dict]:
    """
    Safely get agent output from state.

    Args:
        state: Current state
        agent_name: Name of agent (e.g., "nl_parser")

    Returns:
        Agent output dict if exists, None otherwise

    Example:
        >>> nl_output = get_agent_output(state, "nl_parser")
        >>> if nl_output:
        ...     print(f"Confidence: {nl_output['confidence']}")
    """
    return state.get("agent_outputs", {}).get(agent_name)


def get_agent_confidence(
    state: FamilySchedulerState, agent_name: str
) -> Optional[float]:
    """
    Get confidence score for specific agent output.

    Args:
        state: Current state
        agent_name: Name of agent

    Returns:
        Confidence score (0.0-1.0) if exists, None otherwise

    Example:
        >>> confidence = get_agent_confidence(state, "nl_parser")
        >>> if confidence and confidence < 0.7:
        ...     print("Low confidence, request clarification")
    """
    output = get_agent_output(state, agent_name)
    return output["confidence"] if output else None


def has_blocking_conflicts(state: FamilySchedulerState) -> bool:
    """
    Check if state has blocking conflicts that prevent confirmation.

    Args:
        state: Current state

    Returns:
        True if blocking conflicts exist, False otherwise

    Example:
        >>> if has_blocking_conflicts(state):
        ...     print("Cannot confirm event, conflicts must be resolved")
    """
    conflicts = state.get("detected_conflicts")
    if not conflicts:
        return False

    blocking = conflicts.get("blocking_conflicts", [])
    return len(blocking) > 0


def is_workflow_complete(state: FamilySchedulerState) -> bool:
    """
    Check if workflow has reached a terminal state.

    Args:
        state: Current state

    Returns:
        True if workflow is completed, failed, or awaiting user

    Example:
        >>> if is_workflow_complete(state):
        ...     print("Workflow finished")
    """
    status = state.get("workflow_status")
    return status in ["completed", "failed", "awaiting_user"]


def add_error(
    state: FamilySchedulerState,
    step: str,
    error_type: str,
    message: str,
    retryable: bool = True,
) -> FamilySchedulerState:
    """
    Add error information to state.

    Args:
        state: Current state
        step: Which agent/step failed
        error_type: Type of error
        message: Error message
        retryable: Whether error can be retried

    Returns:
        Updated state

    Example:
        >>> state = add_error(
        ...     state,
        ...     step="nl_parser",
        ...     error_type="parsing_error",
        ...     message="Could not parse time reference",
        ...     retryable=True
        ... )
    """
    error = {
        "step": step,
        "error_type": error_type,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "retryable": retryable,
    }

    if "errors" not in state:
        state["errors"] = []

    state["errors"].append(error)
    state["updated_at"] = datetime.utcnow().isoformat()

    return state


def should_retry(state: FamilySchedulerState, max_retries: int = 3) -> bool:
    """
    Determine if workflow should retry after error.

    Args:
        state: Current state
        max_retries: Maximum number of retries allowed

    Returns:
        True if should retry, False otherwise

    Example:
        >>> if should_retry(state, max_retries=3):
        ...     print("Retrying...")
        ...     state["retry_count"] += 1
    """
    if not state.get("errors"):
        return False

    last_error = state["errors"][-1]
    if not last_error.get("retryable"):
        return False

    retry_count = state.get("retry_count", 0)
    return retry_count < max_retries
