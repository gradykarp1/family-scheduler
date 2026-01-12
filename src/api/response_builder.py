"""
Response builder utilities for transforming orchestrator state to API responses.

Extracts relevant data from FamilySchedulerState and builds WorkflowResponse.
"""

from typing import Any

from src.agents.state import FamilySchedulerState
from src.api.models import WorkflowResponse, WorkflowResult


def build_response(state: FamilySchedulerState) -> WorkflowResponse:
    """
    Build WorkflowResponse from final orchestrator state.

    Args:
        state: Final state from orchestrator invocation

    Returns:
        WorkflowResponse ready for API return
    """
    return WorkflowResponse(
        workflow_id=state.get("conversation_id", "unknown"),
        status=_map_status(state.get("workflow_status", "failed")),
        result=extract_result(state),
        explanation=build_explanation(state),
        agent_outputs=state.get("agent_outputs", {}),
        workflow_steps=extract_steps(state.get("audit_log", [])),
        errors=state.get("errors") if state.get("errors") else None,
    )


def _map_status(workflow_status: str) -> str:
    """Map internal workflow status to API status."""
    status_map = {
        "completed": "completed",
        "in_progress": "completed",  # Should not happen at response time
        "failed": "failed",
        "awaiting_user": "awaiting_user",
    }
    return status_map.get(workflow_status, "failed")


def extract_result(state: FamilySchedulerState) -> WorkflowResult:
    """
    Extract primary result data from state.

    Handles different workflow outcomes:
    - Event created (proposed or confirmed)
    - Conflicts detected
    - Query answered
    - Clarification needed
    """
    proposed_event = state.get("proposed_event")
    detected_conflicts = state.get("detected_conflicts", {})
    agent_outputs = state.get("agent_outputs", {})

    # Check for clarification
    clarification_output = agent_outputs.get("clarification", {})
    clarification_data = clarification_output.get("data", {})

    # Check for query response
    query_output = agent_outputs.get("query", {})
    query_data = query_output.get("data", {})
    query_response = query_data.get("results", {}).get("response")

    # Check for resolution proposals
    resolution_output = agent_outputs.get("resolution", {})
    resolution_data = resolution_output.get("data", {})
    proposed_resolutions = resolution_data.get("proposed_resolutions", [])

    # Build conflicts list
    conflicts = detected_conflicts.get("conflicts", [])
    has_conflicts = detected_conflicts.get("has_conflicts", False)

    return WorkflowResult(
        event=proposed_event,
        conflicts=conflicts,
        proposed_resolutions=proposed_resolutions,
        auto_confirmed=not has_conflicts and proposed_event is not None,
        query_response=query_response,
        clarification_needed=bool(clarification_data),
        clarification_message=clarification_data.get("message"),
    )


def extract_steps(audit_log: list[dict]) -> list[str]:
    """Extract ordered list of workflow steps from audit log."""
    steps = []
    for entry in audit_log:
        step = entry.get("step")
        if step and step not in steps:
            steps.append(step)
    return steps


def build_explanation(state: FamilySchedulerState) -> str:
    """
    Build user-friendly explanation from audit log.

    Combines agent explanations into a narrative of what happened.
    """
    explanations = []

    # Collect explanations from audit log
    for entry in state.get("audit_log", []):
        explanation = entry.get("explanation")
        if explanation:
            explanations.append(explanation)

    # Add final status message
    workflow_status = state.get("workflow_status", "")
    detected_conflicts = state.get("detected_conflicts", {})
    proposed_event = state.get("proposed_event")

    if workflow_status == "completed":
        if proposed_event:
            title = proposed_event.get("title", "Event")
            explanations.append(f"'{title}' has been scheduled")
        elif state.get("agent_outputs", {}).get("query"):
            explanations.append("Query answered")
    elif workflow_status == "awaiting_user":
        if detected_conflicts.get("has_conflicts"):
            conflict_count = len(detected_conflicts.get("conflicts", []))
            explanations.append(f"{conflict_count} conflict(s) detected - please review resolution options")
        elif state.get("agent_outputs", {}).get("clarification"):
            explanations.append("Additional information needed")
    elif workflow_status == "failed":
        errors = state.get("errors", [])
        if errors:
            last_error = errors[-1]
            explanations.append(f"Error: {last_error.get('message', 'Unknown error')}")

    if explanations:
        return " → ".join(explanations)

    return "Workflow completed"


def build_error_response(
    error_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Build standardized error response dictionary."""
    return {
        "error_type": error_type,
        "message": message,
        "details": details,
        "retryable": retryable,
    }
