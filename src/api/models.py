"""
Pydantic request and response models for the Family Scheduler API.

Implements ADR-014: API Endpoint Design & FastAPI Structure.
"""

from typing import Literal, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Request Models
# =============================================================================


class CreateEventRequest(BaseModel):
    """Request to create event from natural language."""

    message: str = Field(
        ...,
        description="Natural language event description",
        min_length=3,
        max_length=500,
        examples=["Schedule soccer practice Saturday at 2pm"],
    )
    user_id: Optional[str] = Field(
        None,
        description="User making request (defaults to default_user)",
    )
    family_id: Optional[str] = Field(
        None,
        description="Family context for event",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Continue previous conversation (multi-turn)",
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ConfirmEventRequest(BaseModel):
    """Request to confirm proposed event."""

    resolution_id: Optional[str] = Field(
        None,
        description="Resolution strategy to apply (if conflicts)",
    )
    user_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="User's reason for confirming",
    )


class ClarifyEventRequest(BaseModel):
    """Request to clarify low-confidence parsing."""

    event_id: str = Field(..., description="Event ID to clarify")
    clarification: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Additional context",
    )
    user_id: Optional[str] = None


class QueryRequest(BaseModel):
    """Natural language query about schedule."""

    message: str = Field(
        ...,
        min_length=3,
        max_length=500,
        examples=["When is everyone free next Saturday?"],
    )
    user_id: Optional[str] = None
    family_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ListEventsRequest(BaseModel):
    """Query parameters for listing events."""

    limit: int = Field(default=50, ge=1, le=100, description="Maximum events to return")
    offset: int = Field(default=0, ge=0, description="Number of events to skip")
    start_date: Optional[str] = Field(
        None,
        description="Filter events starting on or after this date (ISO 8601)",
    )
    end_date: Optional[str] = Field(
        None,
        description="Filter events ending on or before this date (ISO 8601)",
    )
    status: Optional[str] = Field(
        None,
        description="Filter by event status: proposed, confirmed, cancelled",
    )


# =============================================================================
# Response Models
# =============================================================================


class WorkflowStep(BaseModel):
    """Individual step in workflow execution."""

    step: str = Field(..., description="Step name (e.g., 'nl_parsing', 'scheduling')")
    timestamp: str = Field(..., description="When step executed (ISO 8601)")
    agent: str = Field(..., description="Agent that executed step")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent confidence")
    explanation: str = Field(..., description="What the agent did")


class EventResult(BaseModel):
    """Event data in response."""

    id: str = Field(..., description="Event ID")
    title: str = Field(..., description="Event title")
    start_time: Optional[str] = Field(None, description="Start time (ISO 8601)")
    end_time: Optional[str] = Field(None, description="End time (ISO 8601)")
    participants: list[str] = Field(default_factory=list, description="Participant IDs")
    resources: list[str] = Field(default_factory=list, description="Resource IDs")
    status: str = Field(..., description="Event status: proposed, confirmed, cancelled")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class ConflictResult(BaseModel):
    """Conflict information in response."""

    id: str = Field(..., description="Conflict ID")
    type: str = Field(..., description="Conflict type: time_conflict, resource_conflict, constraint_violation")
    severity: str = Field(..., description="Severity: low, medium, high, critical")
    conflicting_event_id: Optional[str] = Field(None, description="ID of conflicting event")
    conflicting_event_title: Optional[str] = Field(None, description="Title of conflicting event")
    description: str = Field(..., description="Human-readable conflict description")


class ResolutionOption(BaseModel):
    """Proposed resolution option."""

    resolution_id: str = Field(..., description="Resolution identifier")
    strategy: str = Field(..., description="Resolution strategy type")
    description: str = Field(..., description="Human-readable description")
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class WorkflowResult(BaseModel):
    """Primary result data from workflow."""

    event: Optional[dict] = Field(None, description="Created/proposed event")
    conflicts: list[dict] = Field(default_factory=list, description="Detected conflicts")
    proposed_resolutions: list[dict] = Field(
        default_factory=list, description="Resolution options (if conflicts)"
    )
    auto_confirmed: bool = Field(
        default=False, description="Whether event was auto-confirmed (no conflicts)"
    )
    query_response: Optional[str] = Field(
        None, description="Query answer (for /query endpoint)"
    )
    clarification_needed: bool = Field(
        default=False, description="Whether clarification is needed"
    )
    clarification_message: Optional[str] = Field(
        None, description="Clarification prompt for user"
    )


class WorkflowResponse(BaseModel):
    """
    Standard response envelope for orchestrator workflows.

    All orchestrator-driven endpoints return this format for consistency.
    """

    workflow_id: str = Field(
        ...,
        description="Conversation ID for tracking and multi-turn context",
    )

    status: Literal["completed", "awaiting_user", "failed"] = Field(
        ...,
        description="Workflow completion status",
    )

    result: WorkflowResult = Field(
        ...,
        description="Main workflow output (event, conflicts, query answer, etc.)",
    )

    explanation: str = Field(
        ...,
        description="Human-readable summary of what happened",
    )

    agent_outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Full outputs from all agents (data, confidence, reasoning)",
    )

    workflow_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of workflow steps executed",
    )

    errors: Optional[list[dict]] = Field(
        None,
        description="Error details if workflow failed",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_id": "conv_abc123",
                "status": "completed",
                "result": {
                    "event": {
                        "id": "event_123",
                        "title": "Soccer practice",
                        "start_time": "2026-01-11T14:00:00Z",
                        "end_time": "2026-01-11T16:00:00Z",
                        "status": "confirmed",
                    },
                    "conflicts": [],
                    "proposed_resolutions": [],
                    "auto_confirmed": True,
                },
                "explanation": "Event created successfully",
                "workflow_steps": [
                    "nl_parsing",
                    "scheduling",
                    "resource_manager",
                    "conflict_detection",
                    "auto_confirm",
                ],
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error information for failed requests."""

    error_type: Literal[
        "validation_error",
        "not_found",
        "agent_failure",
        "database_error",
        "llm_error",
        "timeout_error",
    ] = Field(..., description="Type of error")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    retryable: bool = Field(default=False, description="Whether request can be retried")


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    orchestrator_ready: bool = Field(..., description="Orchestrator initialized")
    database_connected: bool = Field(..., description="Database connection status")


class EventListResponse(BaseModel):
    """Response for listing events."""

    events: list[dict] = Field(..., description="List of events")
    total: int = Field(..., description="Total number of matching events")
    limit: int = Field(..., description="Limit used in query")
    offset: int = Field(..., description="Offset used in query")


class EventDetailResponse(BaseModel):
    """Response for a single event."""

    id: str = Field(..., description="Event ID")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    start_time: str = Field(..., description="Start time (ISO 8601)")
    end_time: str = Field(..., description="End time (ISO 8601)")
    location: Optional[str] = Field(None, description="Event location")
    all_day: bool = Field(default=False, description="Whether this is an all-day event")
    status: str = Field(..., description="Event status")
    calendar_id: str = Field(..., description="Calendar this event belongs to")
    html_link: Optional[str] = Field(None, description="Link to view event in Google Calendar")
    created_at: Optional[str] = Field(None, description="When the event was created")
    updated_at: Optional[str] = Field(None, description="When the event was last updated")


class DeleteEventResponse(BaseModel):
    """Response for deleting an event."""

    success: bool = Field(..., description="Whether deletion was successful")
    event_id: str = Field(..., description="ID of deleted event")
    message: str = Field(..., description="Status message")
