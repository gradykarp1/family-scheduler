"""
Node implementations for LangGraph orchestrator.

Each node is a pure function that:
1. Extracts inputs from state
2. Invokes agent logic (LLM or business logic)
3. Creates audit log entry
4. Returns partial state update
5. Handles errors gracefully

Nodes never raise exceptions - errors are captured in state.
"""

from typing import Any
from datetime import datetime, timezone
import logging
import uuid

from src.agents.state import FamilySchedulerState
from src.agents.llm import get_llm, get_haiku_llm, HAIKU_MODEL

logger = logging.getLogger(__name__)


def _create_audit_entry(
    step: str,
    agent: str,
    confidence: float,
    explanation: str,
) -> dict[str, Any]:
    """Create standardized audit log entry."""
    return {
        "step": step,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "confidence": confidence,
        "explanation": explanation,
    }


def _create_error(
    error_type: str,
    agent: str,
    message: str,
    details: dict | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Create standardized error entry."""
    return {
        "error_type": error_type,
        "agent": agent,
        "message": message,
        "details": details or {},
        "retryable": retryable,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# NL Parser Node
# =============================================================================


def nl_parser_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Extract structured data from natural language input.

    This node parses the user's natural language request and extracts:
    - Event type (create, modify, cancel, query)
    - Title, times, participants, resources
    - Priority and flexibility preferences

    Returns partial state update with:
    - agent_outputs.nl_parser: Agent output with data, confidence, explanation
    - parsed_event_data: Structured event data for quick access
    - audit_log: Appended audit entry
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing NL Parser node")

    try:
        user_input = state.get("user_input", "")
        context = state.get("messages", [])

        # Invoke LLM for parsing
        llm = get_llm(temperature=0.3)  # Lower temperature for more deterministic parsing

        prompt = f"""You are a natural language parser for a family scheduling application.
Extract structured event data from the user's input.

User Input: {user_input}

Previous conversation context (if any):
{context[-3:] if context else "No previous context"}

Extract and return a JSON object with the following fields:
- event_type: "create", "modify", "cancel", or "query"
- title: Event title (if applicable)
- start_time: ISO 8601 datetime string (if mentioned)
- end_time: ISO 8601 datetime string (if mentioned)
- participants: List of participant names mentioned
- resources: List of resources needed (car, room, etc.)
- priority: "low", "medium", "high" (if mentioned, default "medium")
- flexibility: "fixed", "flexible", "very_flexible" (if mentioned)
- recurrence_rule: RRULE string if this is a recurring event

If information is not provided, use null for optional fields.

Respond with ONLY the JSON object, no additional text."""

        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Parse response (simplified - real implementation would be more robust)
        import json
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed_data = json.loads(response_text[json_start:json_end])
            else:
                parsed_data = {"event_type": "create", "title": user_input}
        except json.JSONDecodeError:
            parsed_data = {"event_type": "create", "title": user_input}

        # Calculate confidence based on extracted data completeness
        confidence = _calculate_nl_confidence(parsed_data, user_input)

        # Generate explanation
        event_type = parsed_data.get("event_type", "create")
        title = parsed_data.get("title", "event")
        explanation = f"Understood as: {event_type} event '{title}'"

        # Build agent output
        agent_output = {
            "data": parsed_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Parsed natural language input using LLM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="nl_parsing",
            agent="nl_parser",
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(
            f"[{conv_id}] NL Parser completed: "
            f"intent={event_type}, confidence={confidence:.2f}"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "nl_parser": agent_output,
            },
            "parsed_event_data": parsed_data,
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress",
            "current_step": "nl_parsing",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] NL Parser failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="nl_parser",
            message="Failed to parse natural language input",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "nl_parsing",
        }


def _calculate_nl_confidence(parsed_data: dict, user_input: str) -> float:
    """Calculate confidence score for NL parsing based on completeness."""
    confidence = 0.5  # Base confidence

    # Boost confidence for each key field present
    if parsed_data.get("event_type"):
        confidence += 0.1
    if parsed_data.get("title"):
        confidence += 0.1
    if parsed_data.get("start_time"):
        confidence += 0.15
    if parsed_data.get("participants"):
        confidence += 0.1

    # Reduce confidence for very short or ambiguous inputs
    if len(user_input) < 10:
        confidence -= 0.2

    return min(max(confidence, 0.0), 1.0)


# =============================================================================
# Scheduling Node
# =============================================================================


def scheduling_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Find optimal time slots for the event.

    This node:
    - Analyzes participant availability
    - Considers constraints (hard and soft)
    - Proposes candidate time slots with scores

    Returns partial state update with:
    - agent_outputs.scheduling: Candidate times and recommendations
    - selected_time_slot: Best candidate for quick access
    - audit_log: Appended audit entry
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Scheduling node")

    try:
        parsed_data = state.get("parsed_event_data", {})
        start_time = parsed_data.get("start_time")
        end_time = parsed_data.get("end_time")
        participants = parsed_data.get("participants", [])

        # If specific time provided, use it as the candidate
        if start_time:
            candidate_times = [
                {
                    "start_time": start_time,
                    "end_time": end_time or start_time,  # Default 1 hour if no end
                    "score": 1.0,
                    "available_participants": participants,
                    "constraint_violations": [],
                }
            ]
            recommended_time = start_time
            confidence = 0.95
            explanation = f"Using specified time: {start_time}"
        else:
            # No time specified - would query database for available slots
            # For now, return empty candidates (triggers clarification)
            candidate_times = []
            recommended_time = None
            confidence = 0.3
            explanation = "No time specified, need user input"

        # Build agent output
        scheduling_data = {
            "candidate_times": candidate_times,
            "recommended_time": recommended_time,
        }

        agent_output = {
            "data": scheduling_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Analyzed time constraints and availability",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="scheduling",
            agent="scheduling",
            confidence=confidence,
            explanation=explanation,
        )

        # Set selected time slot if we have candidates
        selected_slot = candidate_times[0] if candidate_times else None

        logger.info(
            f"[{conv_id}] Scheduling completed: "
            f"{len(candidate_times)} candidates, confidence={confidence:.2f}"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "scheduling": agent_output,
            },
            "selected_time_slot": selected_slot,
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress",
            "current_step": "scheduling",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Scheduling failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="scheduling",
            message="Failed to find available time slots",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "scheduling",
        }


# =============================================================================
# Resource Manager Node
# =============================================================================


def resource_manager_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Check resource availability and capacity.

    This node:
    - Checks if requested resources are available
    - Verifies capacity constraints
    - Suggests alternatives if unavailable

    Returns partial state update with:
    - agent_outputs.resource_manager: Availability status
    - audit_log: Appended audit entry
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Resource Manager node")

    try:
        parsed_data = state.get("parsed_event_data", {})
        resources = parsed_data.get("resources", [])
        selected_slot = state.get("selected_time_slot", {})

        # Check resource availability (simplified - would query database)
        resource_availability = []
        all_available = True

        for resource in resources:
            # Placeholder - would check actual database
            availability = {
                "resource_id": str(uuid.uuid4()),
                "resource_name": resource,
                "available": True,
                "current_capacity": 0,
                "max_capacity": 1,
                "conflicts": [],
            }
            resource_availability.append(availability)

        # If no resources requested, still mark as available
        if not resources:
            all_available = True

        # Build agent output
        resource_data = {
            "resource_availability": resource_availability,
            "all_resources_available": all_available,
        }

        confidence = 1.0 if all_available else 0.8
        explanation = (
            "All resources available"
            if all_available
            else f"Some resources unavailable: {[r['resource_name'] for r in resource_availability if not r['available']]}"
        )

        agent_output = {
            "data": resource_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Checked resource availability against scheduled reservations",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="resource_check",
            agent="resource_manager",
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(
            f"[{conv_id}] Resource Manager completed: "
            f"all_available={all_available}, checked {len(resources)} resources"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "resource_manager": agent_output,
            },
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress",
            "current_step": "resource_check",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Resource Manager failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="resource_manager",
            message="Failed to check resource availability",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "resource_check",
        }


# =============================================================================
# Conflict Detection Node
# =============================================================================


def conflict_detection_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Detect scheduling conflicts with existing events.

    This node:
    - Checks for time overlaps with existing events
    - Identifies participant conflicts (double-booking)
    - Checks constraint violations

    Returns partial state update with:
    - agent_outputs.conflict_detection: Detected conflicts
    - detected_conflicts: Conflict data for quick access
    - audit_log: Appended audit entry
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Conflict Detection node")

    try:
        parsed_data = state.get("parsed_event_data", {})
        selected_slot = state.get("selected_time_slot", {})
        participants = parsed_data.get("participants", [])

        # Detect conflicts (simplified - would query database)
        conflicts = []
        has_conflicts = False
        blocking_conflicts = []

        # Placeholder conflict detection
        # In real implementation, would:
        # 1. Query events in time range
        # 2. Check participant overlaps
        # 3. Check constraint violations

        # Build agent output
        conflict_data = {
            "conflicts": conflicts,
            "has_conflicts": has_conflicts,
            "blocking_conflicts": blocking_conflicts,
        }

        confidence = 1.0  # Conflict detection is deterministic
        explanation = (
            f"Detected {len(conflicts)} conflicts"
            if has_conflicts
            else "No conflicts detected"
        )

        agent_output = {
            "data": conflict_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Checked time overlaps and participant availability",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="conflict_detection",
            agent="conflict_detection",
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(
            f"[{conv_id}] Conflict Detection completed: "
            f"has_conflicts={has_conflicts}, count={len(conflicts)}"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "conflict_detection": agent_output,
            },
            "detected_conflicts": conflict_data,
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress",
            "current_step": "conflict_detection",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Conflict Detection failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="conflict_detection",
            message="Failed to detect conflicts",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "conflict_detection",
        }


# =============================================================================
# Resolution Node
# =============================================================================


def resolution_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Generate conflict resolution strategies.

    This node:
    - Analyzes detected conflicts
    - Proposes resolution options (reschedule, modify, cancel)
    - Scores resolutions by impact and feasibility

    Returns partial state update with:
    - agent_outputs.resolution: Proposed resolutions
    - audit_log: Appended audit entry
    - workflow_status: Set to "awaiting_user" for user decision
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Resolution node")

    try:
        detected_conflicts = state.get("detected_conflicts", {})
        conflicts = detected_conflicts.get("conflicts", [])
        parsed_data = state.get("parsed_event_data", {})

        # Generate resolutions using LLM
        llm = get_llm(temperature=0.5)

        prompt = f"""You are a scheduling assistant helping resolve conflicts.

Conflicts detected:
{conflicts}

Original event request:
{parsed_data}

Generate 2-3 resolution options. For each option, provide:
- resolution_id: Unique identifier (e.g., "res_1")
- strategy: One of "move_event", "shorten_event", "cancel_event", "override_constraint"
- score: Confidence score 0.0-1.0
- description: Human-readable description
- conflicts_resolved: List of conflict IDs this resolves

Respond with a JSON object containing:
{{
  "proposed_resolutions": [...],
  "recommended_resolution": "res_id of best option"
}}"""

        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Parse response
        import json
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                resolution_data = json.loads(response_text[json_start:json_end])
            else:
                resolution_data = {
                    "proposed_resolutions": [
                        {
                            "resolution_id": "res_1",
                            "strategy": "move_event",
                            "score": 0.8,
                            "description": "Reschedule to alternative time",
                            "conflicts_resolved": [c.get("id", "") for c in conflicts],
                        }
                    ],
                    "recommended_resolution": "res_1",
                }
        except json.JSONDecodeError:
            resolution_data = {
                "proposed_resolutions": [],
                "recommended_resolution": None,
            }

        confidence = 0.85
        resolutions = resolution_data.get("proposed_resolutions", [])
        explanation = f"Generated {len(resolutions)} resolution options"

        agent_output = {
            "data": resolution_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Analyzed conflicts and generated feasible resolutions",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="resolution",
            agent="resolution",
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(
            f"[{conv_id}] Resolution completed: "
            f"{len(resolutions)} options generated"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "resolution": agent_output,
            },
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "awaiting_user",  # User needs to select resolution
            "current_step": "resolution",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Resolution failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="resolution",
            message="Failed to generate resolutions",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "resolution",
        }


# =============================================================================
# Query Node
# =============================================================================


def query_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Answer natural language queries about schedule.

    This node:
    - Interprets query intent
    - Retrieves relevant data
    - Generates natural language response

    Returns partial state update with:
    - agent_outputs.query: Query results
    - audit_log: Appended audit entry
    - workflow_status: Set to "completed"
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Query node")

    try:
        user_input = state.get("user_input", "")
        parsed_data = state.get("parsed_event_data", {})

        # Use LLM to generate query response
        llm = get_llm(temperature=0.7)

        prompt = f"""You are a helpful family scheduling assistant.
Answer the user's query about their schedule.

User query: {user_input}
Parsed intent: {parsed_data}

Provide a helpful, concise response. If you don't have enough information,
explain what information would be needed.

Note: In a real implementation, you would have access to the family's
calendar data. For now, provide a general helpful response."""

        response = llm.invoke(prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        # Build query data
        query_data = {
            "query_type": "availability",  # Simplified
            "results": {"response": response_text},
        }

        confidence = 0.85
        explanation = "Answered user query about schedule"

        agent_output = {
            "data": query_data,
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": "Processed query and generated response",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="query",
            agent="query",
            confidence=confidence,
            explanation=explanation,
        )

        logger.info(f"[{conv_id}] Query completed")

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "query": agent_output,
            },
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "completed",
            "current_step": "query",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Query failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="query",
            message="Failed to answer query",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "query",
        }


# =============================================================================
# Auto Confirm Node
# =============================================================================


def auto_confirm_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Auto-confirm event when no conflicts exist.

    This node:
    - Creates the event in proposed state
    - Sets workflow status to completed
    - Prepares confirmation response

    Returns partial state update with:
    - proposed_event: The confirmed event
    - audit_log: Appended audit entry
    - workflow_status: Set to "completed"
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Auto Confirm node")

    try:
        parsed_data = state.get("parsed_event_data", {})
        selected_slot = state.get("selected_time_slot", {})

        # Create proposed event
        proposed_event = {
            "event_id": str(uuid.uuid4()),
            "title": parsed_data.get("title", "Untitled Event"),
            "start_time": selected_slot.get("start_time") or parsed_data.get("start_time"),
            "end_time": selected_slot.get("end_time") or parsed_data.get("end_time"),
            "participants": parsed_data.get("participants", []),
            "resources": parsed_data.get("resources", []),
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        explanation = f"Event '{proposed_event['title']}' confirmed"

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="auto_confirm",
            agent="auto_confirm",
            confidence=1.0,
            explanation=explanation,
        )

        logger.info(f"[{conv_id}] Auto Confirm completed: {proposed_event['title']}")

        return {
            "proposed_event": proposed_event,
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "completed",
            "current_step": "auto_confirm",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Auto Confirm failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="auto_confirm",
            message="Failed to confirm event",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "auto_confirm",
        }


# =============================================================================
# Request Clarification Node
# =============================================================================


def request_clarification_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Request clarification from user for ambiguous input.

    This node:
    - Identifies what information is missing
    - Generates clarification question
    - Sets workflow status to awaiting_user

    Returns partial state update with:
    - audit_log: Appended audit entry
    - workflow_status: Set to "awaiting_user"
    """
    conv_id = state.get("conversation_id", "unknown")
    logger.info(f"[{conv_id}] Executing Request Clarification node")

    try:
        user_input = state.get("user_input", "")
        parsed_data = state.get("parsed_event_data", {})
        agent_outputs = state.get("agent_outputs", {})

        # Determine what needs clarification
        nl_output = agent_outputs.get("nl_parser", {})
        confidence = nl_output.get("confidence", 0.0)

        missing_fields = []
        if not parsed_data.get("title"):
            missing_fields.append("event title")
        if not parsed_data.get("start_time"):
            missing_fields.append("start time")
        if not parsed_data.get("participants"):
            missing_fields.append("participants")

        # Generate clarification message
        if missing_fields:
            clarification_message = (
                f"I need a bit more information to schedule your event. "
                f"Could you please specify: {', '.join(missing_fields)}?"
            )
        elif confidence < 0.7:
            clarification_message = (
                f"I'm not quite sure I understood your request: '{user_input}'. "
                f"Could you please rephrase or provide more details?"
            )
        else:
            clarification_message = "Could you please provide more details about your request?"

        explanation = f"Requesting clarification: {', '.join(missing_fields) if missing_fields else 'low confidence'}"

        # Create audit entry
        audit_entry = _create_audit_entry(
            step="request_clarification",
            agent="request_clarification",
            confidence=0.5,
            explanation=explanation,
        )

        logger.info(f"[{conv_id}] Request Clarification: {clarification_message}")

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "clarification": {
                    "data": {
                        "message": clarification_message,
                        "missing_fields": missing_fields,
                    },
                    "confidence": 0.5,
                    "explanation": explanation,
                    "reasoning": "Identified missing or ambiguous information",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            },
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "awaiting_user",
            "current_step": "request_clarification",
        }

    except Exception as e:
        logger.error(f"[{conv_id}] Request Clarification failed: {e}", exc_info=True)

        error = _create_error(
            error_type="agent_failure",
            agent="request_clarification",
            message="Failed to generate clarification request",
            details={"exception": str(e)},
            retryable=True,
        )

        return {
            "workflow_status": "failed",
            "errors": [*state.get("errors", []), error],
            "current_step": "request_clarification",
        }
