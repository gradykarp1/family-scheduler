"""
LangGraph state schema definitions for Family Scheduler.

This module defines the centralized state structure that flows through the
orchestrator and all agents. It implements ADR-012: LangGraph State Schema Design.

Design Rationale:
- TypedDict root state for LangGraph compatibility and partial updates
- Pydantic models for nested structures to provide validation
- Namespaced agent outputs to prevent collisions
- ISO 8601 datetime strings for JSON serialization
- Implements ADR-004 hybrid output format (data + explanation)
"""

from typing import TypedDict, Annotated, Sequence, Optional, Literal, Any
from pydantic import BaseModel, Field


# ============================================================================
# Message and Conversation
# ============================================================================

class Message(BaseModel):
    """Single message in conversation history."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str  # ISO 8601 format


# ============================================================================
# Agent Output Standard (ADR-004: Hybrid Format)
# ============================================================================

class AgentOutput(BaseModel):
    """
    Standard output format for all agents (implements ADR-004).

    Each agent returns:
    - Structured data (for orchestrator decisions)
    - Natural language explanation (for user communication)
    - Confidence score (for routing decisions)
    - Reasoning (for debugging/audit)
    """

    data: dict  # Agent-specific structured data
    explanation: str  # Human-readable summary of what agent did
    confidence: float = Field(ge=0.0, le=1.0)  # Confidence in output (0.0-1.0)
    reasoning: str  # Why agent made this decision
    timestamp: str  # ISO 8601 format - when output was generated


# ============================================================================
# NL Parser Agent Models
# ============================================================================

class NLParserData(BaseModel):
    """Structured data from NL Parser Agent."""

    event_type: Literal["create", "modify", "cancel", "query"]
    title: Optional[str] = None
    start_time: Optional[str] = None  # ISO 8601 format
    end_time: Optional[str] = None  # ISO 8601 format
    participants: list[str] = Field(default_factory=list)  # Family member IDs
    resources: list[str] = Field(default_factory=list)  # Resource IDs
    recurrence_rule: Optional[str] = None  # RRULE format (ADR-007)
    priority: Optional[str] = None
    flexibility: Optional[str] = None  # How flexible is user on timing


# ============================================================================
# Scheduling Agent Models
# ============================================================================

class TimeSlot(BaseModel):
    """Individual time slot candidate."""

    start_time: str  # ISO 8601
    end_time: str  # ISO 8601
    score: float  # Optimization score
    available_participants: list[str]
    constraint_violations: list[str]  # Any soft constraints violated


class SchedulingData(BaseModel):
    """Structured data from Scheduling Agent."""

    candidate_times: list[TimeSlot]
    recommended_time: Optional[str] = None  # ISO 8601 (best candidate)


# ============================================================================
# Resource Manager Agent Models
# ============================================================================

class ResourceAvailability(BaseModel):
    """Resource availability status."""

    resource_id: str
    resource_name: str
    available: bool
    current_capacity: int
    max_capacity: int
    conflicts: list[str]  # Conflicting event IDs


class ResourceManagerData(BaseModel):
    """Structured data from Resource Manager Agent."""

    resource_availability: list[ResourceAvailability]
    all_resources_available: bool


# ============================================================================
# Conflict Detection Agent Models
# ============================================================================

class Conflict(BaseModel):
    """Individual conflict detected."""

    id: str
    type: Literal["time_conflict", "resource_conflict", "constraint_violation"]
    severity: Literal["low", "medium", "high", "critical"]
    conflicting_event_id: Optional[str] = None
    conflicting_event_title: Optional[str] = None
    participants_affected: list[str] = Field(default_factory=list)
    details: str


class ConflictDetectionData(BaseModel):
    """Structured data from Conflict Detection Agent."""

    conflicts: list[Conflict]
    has_conflicts: bool
    blocking_conflicts: list[str]  # IDs of conflicts that block confirmation


# ============================================================================
# Resolution Agent Models
# ============================================================================

class ResolutionChange(BaseModel):
    """Individual change proposed in resolution."""

    event_id: Optional[str] = None
    field: Optional[str] = None  # e.g., "start_time"
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    action: Optional[Literal["move", "cancel", "shorten", "split"]] = None


class ProposedResolution(BaseModel):
    """Single resolution option."""

    resolution_id: str
    strategy: Literal[
        "move_event",
        "shorten_event",
        "split_event",
        "cancel_event",
        "override_constraint",
        "alternative_resource",
    ]
    score: float
    description: str
    changes: list[ResolutionChange]
    conflicts_resolved: list[str]  # Conflict IDs resolved
    side_effects: list[str]  # Any negative side effects


class ResolutionData(BaseModel):
    """Structured data from Resolution Agent."""

    proposed_resolutions: list[ProposedResolution]
    recommended_resolution: Optional[str] = None  # resolution_id


# ============================================================================
# Query Agent Models
# ============================================================================

class QueryData(BaseModel):
    """Structured data from Query Agent."""

    query_type: Literal["availability", "event_lookup", "resource_status", "conflict_check"]
    results: dict  # Flexible results based on query type


# ============================================================================
# Proposal Flow Models (ADR-003)
# ============================================================================

class ProposedEvent(BaseModel):
    """Event in proposed state."""

    event_id: str  # Database ID of proposed event
    title: str
    start_time: str  # ISO 8601
    end_time: str  # ISO 8601
    participants: list[str]
    resources: list[str]
    status: Literal["proposed", "validated", "confirmed", "rejected"]
    created_at: str  # ISO 8601


class ValidationResult(BaseModel):
    """Validation step result."""

    step: Literal[
        "nl_parsing",
        "scheduling",
        "resource_check",
        "conflict_detection",
        "resolution",
    ]
    passed: bool
    timestamp: str  # ISO 8601
    issues: list[str] = Field(default_factory=list)


# ============================================================================
# Error Tracking
# ============================================================================

class ErrorInfo(BaseModel):
    """Error information."""

    step: str  # Which agent/step failed
    error_type: str  # Type of error
    message: str  # Error message
    timestamp: str  # ISO 8601
    retryable: bool  # Can this be retried?


# ============================================================================
# Root State Definition (TypedDict)
# ============================================================================

class FamilySchedulerState(TypedDict, total=False):
    """
    Root state for LangGraph orchestration.

    Design rationale:
    - TypedDict with total=False allows partial updates from agents
    - JSON serializable for LangGraph checkpoints
    - Compatible with LangGraph StateGraph
    - Namespaced agent outputs prevent collisions

    Each workflow invocation gets its own state instance - states are isolated
    per conversation/request, enabling concurrent execution.

    Example usage:
        >>> state = FamilySchedulerState(
        ...     user_input="Schedule soccer practice Saturday at 2pm",
        ...     user_id="user_123",
        ...     conversation_id="conv_456",
        ...     current_step="start",
        ...     workflow_status="in_progress",
        ...     agent_outputs={},
        ...     validation_results=[],
        ...     errors=[],
        ...     retry_count=0,
        ...     messages=[],
        ...     audit_log=[],
        ...     created_at="2026-01-08T20:00:00Z",
        ...     updated_at="2026-01-08T20:00:00Z"
        ... )
    """

    # === User Input & Context ===
    user_input: str  # Original natural language request
    user_id: str  # Family member making the request
    conversation_id: str  # For tracking multi-turn conversations

    # === Workflow Control ===
    current_step: str  # Current workflow step (e.g., "nl_parsing", "scheduling")
    workflow_status: Literal["in_progress", "completed", "failed", "awaiting_user"]
    next_action: Optional[str]  # Next step to execute (for orchestrator)

    # === Conversation History ===
    # Uses LangGraph's add_messages reducer for proper message handling
    messages: Sequence[dict]  # List of Message dictionaries

    # === Agent Outputs (Namespaced) ===
    # Keys: "nl_parser", "scheduling", "resource_manager", "conflict_detection",
    #       "resolution", "query"
    # Values: AgentOutput dictionaries
    agent_outputs: dict[str, dict]

    # === Proposal Flow (ADR-003) ===
    proposed_event: Optional[dict]  # ProposedEvent dictionary
    validation_results: list[dict]  # List of ValidationResult dictionaries

    # === Convenience Fields (Quick Access) ===
    parsed_event_data: Optional[dict]  # NLParserData for quick access
    selected_time_slot: Optional[dict]  # Chosen TimeSlot
    detected_conflicts: Optional[dict]  # ConflictDetectionData
    selected_resolution: Optional[dict]  # User-selected ProposedResolution

    # === Error Tracking ===
    errors: list[dict]  # List of ErrorInfo dictionaries
    retry_count: int

    # === Metadata ===
    created_at: str  # ISO 8601 format
    updated_at: str  # ISO 8601 format
    audit_log: list[dict[str, Any]]  # Workflow step history
