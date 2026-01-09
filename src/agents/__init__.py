"""
Agent module for Family Scheduler.

This module provides LangGraph state definitions, state utilities,
and agent implementations for the Family Scheduler system.

Implements ADR-012: LangGraph State Schema Design
"""

from src.agents.state import (
    # Root State
    FamilySchedulerState,
    # Standard Agent Output
    AgentOutput,
    # NL Parser Models
    NLParserData,
    # Scheduling Models
    TimeSlot,
    SchedulingData,
    # Resource Manager Models
    ResourceAvailability,
    ResourceManagerData,
    # Conflict Detection Models
    Conflict,
    ConflictDetectionData,
    # Resolution Models
    ResolutionChange,
    ProposedResolution,
    ResolutionData,
    # Query Models
    QueryData,
    # Proposal Flow Models
    ProposedEvent,
    ValidationResult,
    # Error and Message Models
    ErrorInfo,
    Message,
)

from src.agents.state_utils import (
    # State Initialization
    initialize_state,
    # State Updates
    update_state_with_agent_output,
    transition_workflow_step,
    # State Validation
    validate_state_transition,
    # State Optimization
    prune_state,
    # State Accessors
    get_agent_output,
    get_agent_confidence,
    has_blocking_conflicts,
    is_workflow_complete,
    # Error Handling
    add_error,
    should_retry,
)

__all__ = [
    # Root State
    "FamilySchedulerState",
    # Standard Agent Output
    "AgentOutput",
    # NL Parser Models
    "NLParserData",
    # Scheduling Models
    "TimeSlot",
    "SchedulingData",
    # Resource Manager Models
    "ResourceAvailability",
    "ResourceManagerData",
    # Conflict Detection Models
    "Conflict",
    "ConflictDetectionData",
    # Resolution Models
    "ResolutionChange",
    "ProposedResolution",
    "ResolutionData",
    # Query Models
    "QueryData",
    # Proposal Flow Models
    "ProposedEvent",
    "ValidationResult",
    # Error and Message Models
    "ErrorInfo",
    "Message",
    # State Utilities
    "initialize_state",
    "update_state_with_agent_output",
    "transition_workflow_step",
    "validate_state_transition",
    "prune_state",
    "get_agent_output",
    "get_agent_confidence",
    "has_blocking_conflicts",
    "is_workflow_complete",
    "add_error",
    "should_retry",
]
