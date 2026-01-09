# ADR-012: LangGraph State Schema Design

## Status
Implemented

**Implementation Status**: Implemented
**Implementation Date**: 2026-01-08

## Context

The Family Scheduler uses a hub-and-spoke agent architecture with LangGraph orchestration. The central orchestrator coordinates 6 specialized agents:
- **NL Parser Agent**: Extracts structured data from natural language input
- **Scheduling Agent**: Finds optimal time slots based on constraints
- **Resource Manager Agent**: Checks resource availability and capacity
- **Conflict Detection Agent**: Identifies scheduling conflicts
- **Resolution Agent**: Generates intelligent conflict resolution strategies
- **Query Agent**: Answers natural language questions about schedules

All of these agents must share state through a centralized state object that flows through the LangGraph workflow. The state schema design is the most critical technical decision blocking agent implementation.

### Requirements for State Schema

**From Architecture Decisions:**
- **ADR-002 (Hub-and-Spoke)**: Requires centralized state for orchestrator coordination
- **ADR-003 (Proposal Flow)**: Must track events through proposed → validated → confirmed pipeline
- **ADR-004 (Hybrid Output Format)**: Each agent returns structured data + natural language explanation
- **ADR-005 (Conflict Detection)**: Needs to track validation results and conflict information

**From LangGraph Requirements:**
- Must be compatible with LangGraph's StateGraph (TypedDict or Pydantic)
- Must be JSON serializable for checkpoints and persistence
- Should support partial updates from individual agents
- Must work with LangGraph's message handling patterns

**From Multi-Agent Coordination:**
- 6 agents need to contribute outputs without namespace collisions
- Orchestrator must read agent outputs to make routing decisions
- Agent outputs must include both data and explanations (ADR-004)
- Must support confidence scores for decision-making

**From Conversation & Error Handling:**
- Multi-turn conversation history for context
- Error tracking and retry logic
- Audit trail for debugging and observability
- Workflow status tracking (in_progress, completed, failed, awaiting_user)

**From Proposal Flow (ADR-003):**
- Track proposed events through validation pipeline
- Store validation results from each agent
- Support event confirmation after successful validation

### Key Challenges

1. **Namespace Collisions**: How to prevent agents from overwriting each other's outputs?
2. **State Size**: How to keep state manageable while including full context for orchestrator?
3. **Serialization**: How to handle datetime objects and complex nested structures?
4. **Type Safety**: How to ensure agents produce correctly structured outputs?
5. **LangGraph Integration**: What patterns work best with LangGraph's StateGraph?
6. **Concurrency**: How does state handle multiple simultaneous user requests?

## Decision

We will use a **TypedDict root state with namespaced agent outputs and Pydantic models for nested structures**.

### State Schema Design

#### Root State: TypedDict

```python
from typing import TypedDict, Annotated, Sequence, Optional, Literal, Any
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

class FamilySchedulerState(TypedDict, total=False):
    """
    Root state for LangGraph orchestration.

    Design rationale:
    - TypedDict with total=False allows partial updates from agents
    - JSON serializable for LangGraph checkpoints
    - Compatible with LangGraph StateGraph
    - Namespaced agent outputs prevent collisions
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
    messages: Annotated[Sequence[dict], add_messages]

    # === Agent Outputs (Namespaced) ===
    agent_outputs: dict[str, dict]  # Keys: "nl_parser", "scheduling", etc.
                                     # Values: AgentOutput dictionaries

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
```

**Key Design Choice: TypedDict over Pydantic**
- LangGraph has first-class support for TypedDict
- `total=False` enables partial updates (agents only update their namespace)
- Better JSON serialization for checkpoints
- Pydantic models used for nested structures (validation without immutability issues)

#### Agent Output Standard (ADR-004 Hybrid Format)

```python
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
```

#### Agent-Specific Data Models

**NL Parser Data**:
```python
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
```

**Scheduling Data**:
```python
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
```

**Resource Manager Data**:
```python
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
```

**Conflict Detection Data**:
```python
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
```

**Resolution Data**:
```python
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
    strategy: Literal["move_event", "shorten_event", "split_event",
                     "cancel_event", "override_constraint", "alternative_resource"]
    score: float
    description: str
    changes: list[ResolutionChange]
    conflicts_resolved: list[str]  # Conflict IDs resolved
    side_effects: list[str]  # Any negative side effects

class ResolutionData(BaseModel):
    """Structured data from Resolution Agent."""
    proposed_resolutions: list[ProposedResolution]
    recommended_resolution: Optional[str] = None  # resolution_id
```

**Query Data**:
```python
class QueryData(BaseModel):
    """Structured data from Query Agent."""
    query_type: Literal["availability", "event_lookup", "resource_status", "conflict_check"]
    results: dict  # Flexible results based on query type
```

#### Proposal Flow Models (ADR-003)

```python
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
    step: Literal["nl_parsing", "scheduling", "resource_check",
                 "conflict_detection", "resolution"]
    passed: bool
    timestamp: str  # ISO 8601
    issues: list[str] = Field(default_factory=list)
```

#### Error Tracking

```python
class ErrorInfo(BaseModel):
    """Error information."""
    step: str  # Which agent/step failed
    error_type: str  # Type of error
    message: str  # Error message
    timestamp: str  # ISO 8601
    retryable: bool  # Can this be retried?
```

#### Message Format

```python
class Message(BaseModel):
    """Single message in conversation history."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str  # ISO 8601
```

### Namespacing Strategy

**Decision: Single `agent_outputs` dict with agent names as keys**

```python
# Example state after NL Parser runs:
state["agent_outputs"]["nl_parser"] = {
    "data": {
        "event_type": "create",
        "title": "Soccer practice",
        "start_time": "2026-01-11T14:00:00Z",
        # ...
    },
    "explanation": "Parsed as a new event creation for Saturday at 2pm",
    "confidence": 0.95,
    "reasoning": "Clear time reference and event type",
    "timestamp": "2026-01-08T20:30:00Z"
}

# After Scheduling Agent runs:
state["agent_outputs"]["scheduling"] = {
    "data": {
        "candidate_times": [...],
        "recommended_time": "2026-01-11T14:00:00Z"
    },
    "explanation": "Found 3 available time slots, recommending Saturday 2pm",
    "confidence": 0.88,
    "reasoning": "All participants available, no hard conflicts",
    "timestamp": "2026-01-08T20:30:15Z"
}
```

**Benefits**:
- Clear ownership per agent
- No namespace collisions
- Easy to inspect what each agent contributed
- Supports dynamic agent addition

### Datetime Serialization Strategy

**Decision: Store all datetimes as ISO 8601 strings**

```python
from datetime import datetime

# When creating timestamps:
timestamp = datetime.utcnow().isoformat()  # "2026-01-08T20:30:45.123456"

# When parsing back:
dt = datetime.fromisoformat(timestamp)
```

**Rationale**:
- JSON serializable (required for LangGraph checkpoints)
- Human readable in logs
- Consistent format across all agents
- Easy to parse back to datetime objects
- Supports timezone information

### State Update Pattern

```python
from datetime import datetime

def update_state_with_agent_output(
    state: FamilySchedulerState,
    agent_name: str,
    output: AgentOutput
) -> FamilySchedulerState:
    """
    Standard pattern for agents to update state.

    Args:
        state: Current state
        agent_name: Name of agent (e.g., "nl_parser")
        output: Agent's output conforming to AgentOutput model

    Returns:
        Updated state
    """
    # Convert Pydantic model to dict for TypedDict compatibility
    state["agent_outputs"][agent_name] = output.model_dump()
    state["updated_at"] = datetime.utcnow().isoformat()

    # Add to audit log
    state["audit_log"].append({
        "step": agent_name,
        "timestamp": output.timestamp,
        "confidence": output.confidence,
        "explanation": output.explanation
    })

    return state
```

### Concurrency Model

**How Multiple Requests Are Handled:**

Each workflow invocation gets its own state instance. The agent names in `agent_outputs` are just namespace keys within a single state object for one user request.

```python
# User 1 makes a request (separate state instance)
state_user1 = FamilySchedulerState(
    user_input="Schedule soccer Saturday at 2pm",
    conversation_id="conv_123",
    agent_outputs={}
)
result1 = app.invoke(state_user1, config={"configurable": {"thread_id": "conv_123"}})

# User 2 makes a request simultaneously (separate state instance)
state_user2 = FamilySchedulerState(
    user_input="When is dinner scheduled?",
    conversation_id="conv_456",
    agent_outputs={}
)
result2 = app.invoke(state_user2, config={"configurable": {"thread_id": "conv_456"}})

# These are completely independent - no interference
```

**Key Points**:
- Each `app.invoke()` creates an isolated execution context
- State instances are independent per conversation/request
- `thread_id` in config ensures separate checkpoints
- Multiple users can interact with the system simultaneously
- Each agent execution within a workflow updates that workflow's state only

### LangGraph Integration Example

```python
from langgraph.graph import StateGraph, END

# Define the graph with our state schema
workflow = StateGraph(FamilySchedulerState)

# Add agent nodes
workflow.add_node("nl_parser", nl_parser_agent)
workflow.add_node("scheduling", scheduling_agent)
workflow.add_node("resource_manager", resource_manager_agent)
workflow.add_node("conflict_detection", conflict_detection_agent)
workflow.add_node("resolution", resolution_agent)

# Define routing logic
def route_next_step(state: FamilySchedulerState) -> str:
    """Orchestrator routing logic based on state."""
    current = state["current_step"]

    if current == "start":
        return "nl_parser"

    elif current == "nl_parsing":
        nl_output = state["agent_outputs"].get("nl_parser")
        if nl_output and nl_output["confidence"] < 0.7:
            return "request_clarification"
        return "scheduling"

    elif current == "scheduling":
        return "resource_manager"

    elif current == "resource_manager":
        return "conflict_detection"

    elif current == "conflict_detection":
        conflicts = state.get("detected_conflicts")
        if conflicts and conflicts.get("has_conflicts"):
            return "resolution"
        return "confirm_event"

    return END

# Add conditional edges
workflow.add_conditional_edges("nl_parser", route_next_step)
workflow.add_conditional_edges("scheduling", route_next_step)
# ...

# Set entry point
workflow.set_entry_point("nl_parser")

# Compile
app = workflow.compile()
```

### State Size Optimization

**Problem**: State can grow large with full agent outputs

**Solutions**:

1. **Pruning Old Data**:
```python
def prune_state(state: FamilySchedulerState) -> FamilySchedulerState:
    """Remove old/unnecessary data from state."""
    # Keep only last 10 messages
    if len(state.get("messages", [])) > 10:
        state["messages"] = state["messages"][-10:]

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
                "timestamp": agent_out["timestamp"]
            }

    return state
```

2. **Checkpoint Compression**:
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# For development
memory = SqliteSaver.from_conn_string(":memory:")

# For production
memory = SqliteSaver.from_conn_string("checkpoints.db")

app = workflow.compile(checkpointer=memory)
```

## Consequences

### Positive

1. **Clear Ownership**: Each agent has a dedicated namespace in `agent_outputs`, making it clear who produced what data

2. **Type Safety**: Pydantic models validate nested structures, catching errors early in development

3. **Partial Updates**: TypedDict with `total=False` allows agents to update only their section without reconstructing entire state

4. **Scalable**: Easy to add new agents without restructuring existing state - just add a new key to `agent_outputs`

5. **LangGraph Optimized**: Uses recommended patterns (TypedDict root, `add_messages` reducer)

6. **JSON Serializable**: Everything serializes to JSON automatically for LangGraph checkpoints

7. **Audit Trail**: Built-in workflow history tracking in `audit_log` for debugging

8. **Testable**: Clear state contracts enable robust testing with fixtures

9. **Concurrent**: Each workflow invocation gets isolated state instance - no interference between requests

10. **Hybrid Format Compliant**: Implements ADR-004 standard (structured data + explanation)

11. **Proposal Flow Support**: Dedicated fields for tracking events through validation pipeline (ADR-003)

### Negative

1. **Nesting Complexity**: Accessing nested data requires multiple levels (e.g., `state["agent_outputs"]["nl_parser"]["data"]["title"]`)

2. **State Size**: Full agent outputs can grow large with many candidate times or resolutions

3. **Validation Overhead**: Pydantic validation on every nested update adds some processing time

4. **Learning Curve**: Team must understand namespacing pattern and state structure

5. **TypedDict vs Pydantic Mismatch**: Root is TypedDict, nested is Pydantic - requires conversion (.model_dump())

### Mitigation Strategies

**For Nesting Complexity**:
- Provide helper functions in `state_utils.py` for common access patterns
- Use convenience fields (`parsed_event_data`, `selected_time_slot`) for frequently accessed data
- Document common patterns in usage examples

**For State Size**:
- Implement pruning functions for old conversation history
- Use checkpoint compression in production
- Consider external storage (Redis) for very large datasets in future

**For Validation Overhead**:
- Use Pydantic V2 which is significantly faster
- Profile performance and optimize hot paths
- Acceptable trade-off for type safety in a learning project

**For Learning Curve**:
- Create comprehensive documentation with examples
- Provide usage patterns for common operations
- Include state diagram in documentation

**For TypedDict/Pydantic Conversion**:
- Use `.model_dump()` consistently in helper functions
- Document pattern clearly
- Consider upgrading to full Pydantic root in future if TypedDict limitations become problematic

## Alternatives Considered

### Alternative 1: Flat State Structure

**Approach**: All fields at root level

```python
class FlatState(TypedDict):
    user_input: str
    nl_parser_data: dict
    nl_parser_confidence: float
    nl_parser_explanation: str
    scheduling_data: dict
    scheduling_confidence: float
    scheduling_explanation: str
    # ... 20+ more fields
```

**Pros**:
- Simpler structure
- Direct field access (no nesting)
- Slightly faster access

**Cons**:
- No clear namespace separation - collision risk
- Difficult to track which agent produced what
- Doesn't scale - adding 7th agent means 4+ more root fields
- Poor organization - 30+ root-level fields
- Loses agent ownership attribution

**Why Not Chosen**: Doesn't scale with 6+ agents, loses clear ownership tracking, becomes unwieldy with growth

### Alternative 2: Pydantic Root Model

**Approach**: Use Pydantic BaseModel for entire state

```python
class FamilySchedulerState(BaseModel):
    user_input: str
    agent_outputs: dict[str, AgentOutput]
    # ... etc
```

**Pros**:
- Full validation on every update
- Better type hints and IDE support
- Built-in serialization methods
- Immutability prevents accidental mutations

**Cons**:
- LangGraph documentation favors TypedDict
- Immutability complicates partial updates from agents
- Additional conversion overhead
- Less idiomatic for LangGraph patterns

**Why Not Chosen**: TypedDict is more idiomatic for LangGraph; Pydantic's immutability makes partial updates more complex. Use Pydantic for nested structures where validation is key.

### Alternative 3: Separate State per Agent

**Approach**: Each agent maintains independent state object

```python
nl_parser_state = NLParserState(...)
scheduling_state = SchedulingState(...)
# Orchestrator manages separate states
```

**Pros**:
- Clear separation of concerns
- Independent state evolution per agent
- No namespace collisions possible

**Cons**:
- Difficult to share context between agents
- Complex orchestrator logic to merge/pass states
- No unified state view for debugging
- Doesn't fit hub-and-spoke architecture

**Why Not Chosen**: Hub-and-spoke architecture (ADR-002) requires centralized state for orchestrator to make routing decisions based on all agent outputs

### Alternative 4: Store References Only (Database IDs)

**Approach**: Agent outputs just store database IDs, query DB for full data

```python
state["agent_outputs"]["scheduling"] = {
    "candidate_time_ids": ["id1", "id2", "id3"],  # Just IDs
    "recommended_time_id": "id1"
}
```

**Pros**:
- Minimal state size
- No data duplication
- Always fresh data from database

**Cons**:
- Orchestrator needs many database queries for routing decisions
- Added latency for each decision
- Tight coupling to database
- Stale data risk if database changes mid-workflow
- Complicates testing (need database)

**Why Not Chosen**: Orchestrator needs rich data to make routing decisions (confidence scores, constraint violations, etc.). Database queries would add significant latency and complexity. State is ephemeral - database is persistent.

### Alternative 5: Separate Metadata and Data Layers

**Approach**: Split state into metadata layer and data layer

```python
class StateMetadata(TypedDict):
    current_step: str
    workflow_status: str
    # ... control fields only

class StateData(TypedDict):
    agent_outputs: dict
    # ... data fields only
```

**Pros**:
- Clear separation of control vs data
- Could optimize metadata updates separately

**Cons**:
- Added complexity with two state objects
- Orchestrator needs both for decisions
- Not a common LangGraph pattern
- Unclear benefit for state size

**Why Not Chosen**: Added complexity without clear benefit. Single state object is simpler and sufficient.

## Implementation Notes

### File Structure

```
src/agents/
├── __init__.py
├── state.py                    # State definitions (TypedDict + Pydantic models)
├── state_utils.py              # State update helpers
├── orchestrator.py             # LangGraph workflow (future)
├── nl_parser_agent.py          # NL Parser (future)
├── scheduling_agent.py         # Scheduling (future)
├── resource_manager_agent.py   # Resource Manager (future)
├── conflict_detection_agent.py # Conflict Detection (future)
├── resolution_agent.py         # Resolution (future)
└── query_agent.py              # Query (future)
```

### Critical Implementation Details

**1. Import Pattern**:
```python
# src/agents/__init__.py
from src.agents.state import (
    FamilySchedulerState,
    AgentOutput,
    NLParserData,
    SchedulingData,
    ResourceManagerData,
    ConflictDetectionData,
    ResolutionData,
    QueryData,
    ProposedEvent,
    ValidationResult,
    ErrorInfo,
    Message,
    TimeSlot,
    Conflict,
    ResourceAvailability,
    ResolutionChange,
    ProposedResolution,
)

__all__ = [
    "FamilySchedulerState",
    "AgentOutput",
    # ... all models
]
```

**2. State Initialization Helper**:
```python
from datetime import datetime
import uuid

def initialize_state(user_input: str, user_id: str) -> FamilySchedulerState:
    """Create fresh state for new workflow."""
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
        audit_log=[]
    )
```

**3. State Validation Helper**:
```python
def validate_state_transition(
    state: FamilySchedulerState,
    next_step: str
) -> tuple[bool, Optional[str]]:
    """
    Validate state before transition.

    Returns:
        (is_valid, error_message)
    """
    if next_step == "scheduling":
        if "nl_parser" not in state.get("agent_outputs", {}):
            return False, "NL Parser output required for scheduling"

        nl_output = state["agent_outputs"]["nl_parser"]
        if nl_output["confidence"] < 0.5:
            return False, f"NL Parser confidence too low: {nl_output['confidence']}"

    elif next_step == "conflict_detection":
        required = ["nl_parser", "scheduling", "resource_manager"]
        missing = [a for a in required if a not in state.get("agent_outputs", {})]
        if missing:
            return False, f"Missing required agents: {missing}"

    return True, None
```

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangGraph State Management](https://python.langchain.com/docs/langgraph#state)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [TypedDict Documentation](https://docs.python.org/3/library/typing.html#typing.TypedDict)
- [ADR-002: Hub-and-Spoke Agent Architecture](./adr-002-hub-and-spoke-agent-architecture.md)
- [ADR-003: Proposal Flow for Event Creation](./adr-003-proposal-flow-for-event-creation.md)
- [ADR-004: Hybrid Agent Output Format](./adr-004-hybrid-agent-output-format.md)
- [ADR-010: Python Environment & Package Management](./adr-010-python-environment-package-management.md)
- [ADR-011: LLM Provider Selection](./adr-011-llm-provider-selection.md)

## Implementation

**Implemented**: 2026-01-08

### What Was Created

1. **State Definitions** (`src/agents/state.py`)
   - FamilySchedulerState TypedDict with all root fields
   - AgentOutput Pydantic model implementing ADR-004 hybrid format
   - Complete Pydantic models for all 6 agent types:
     - NLParserData with event_type, title, participants, resources, etc.
     - TimeSlot, SchedulingData for Scheduling Agent
     - ResourceAvailability, ResourceManagerData for Resource Manager
     - Conflict, ConflictDetectionData for Conflict Detection
     - ResolutionChange, ProposedResolution, ResolutionData for Resolution Agent
     - QueryData for Query Agent
   - ProposedEvent, ValidationResult for Proposal Flow (ADR-003)
   - ErrorInfo, Message for error tracking and conversation
   - All models include comprehensive docstrings and examples

2. **State Utilities** (`src/agents/state_utils.py`)
   - `initialize_state()`: Create fresh state for new workflows
   - `update_state_with_agent_output()`: Standard pattern for agent updates
   - `transition_workflow_step()`: Workflow step transitions with audit logging
   - `validate_state_transition()`: Pre-transition validation logic
   - `prune_state()`: State size optimization
   - Helper functions: `get_agent_output()`, `get_agent_confidence()`, `has_blocking_conflicts()`, `is_workflow_complete()`, `add_error()`, `should_retry()`
   - All functions include comprehensive docstrings and examples

3. **Unit Tests** (`tests/unit/test_state.py`)
   - 29 comprehensive unit tests covering:
     - Pydantic model validation (AgentOutput, NLParserData, Conflict, etc.)
     - State initialization
     - State updates from multiple agents
     - Workflow transitions
     - State validation logic
     - State pruning operations
     - State accessor functions
     - Conflict and error handling
     - JSON serialization
   - All tests passing (100% success rate)

4. **Usage Documentation** (`docs/examples/state_usage.md`)
   - Comprehensive examples for all common operations:
     - Initializing state
     - Agent updates (NL Parser, Scheduling, Conflict Detection)
     - Orchestrator routing patterns
     - Error handling and retry logic
     - Multi-turn conversations
     - State pruning strategies
     - Complete end-to-end workflow example
   - Best practices and debugging tips

5. **Module Exports** (`src/agents/__init__.py`)
   - Centralized exports of all state types and utilities
   - Clear organization with comments
   - Comprehensive `__all__` list for clean imports

6. **Documentation Updates**
   - Added ADR-012 to `docs/decisions/README.md` index
   - Created `docs/examples/` directory for usage patterns

### Deviations from Plan

**None** - Implementation followed the ADR exactly as planned.

All design decisions were implemented as specified:
- TypedDict root state ✅
- Namespaced agent outputs with single `agent_outputs` dict ✅
- Pydantic models for nested structures ✅
- ISO 8601 datetime strings ✅
- Hybrid output format (ADR-004) ✅
- Proposal flow integration (ADR-003) ✅
- Comprehensive state utilities ✅
- Full test coverage ✅

### Lessons Learned

1. **TypedDict + Pydantic Works Well**: Using TypedDict for the root with Pydantic for nested structures provides excellent balance of flexibility and type safety. The `.model_dump()` conversion is straightforward.

2. **State Utilities Critical**: Helper functions like `update_state_with_agent_output()` and `validate_state_transition()` make working with state much cleaner. Future agent implementations will benefit greatly from these patterns.

3. **Comprehensive Testing Pays Off**: Writing 29 unit tests during implementation caught several edge cases (confidence validation, empty state handling, pruning logic) that would have caused runtime errors.

4. **Documentation by Example**: The `state_usage.md` file with concrete examples is invaluable. Writing these examples revealed several usability improvements (accessor functions, validation helpers).

5. **Audit Log Valuable**: Including `audit_log` in state design enables powerful debugging and observability. Every state transition and agent invocation is tracked.

6. **Pruning Important**: State size can grow quickly with conversation history and agent outputs. The pruning strategy (clear data after extraction to convenience fields) keeps state manageable while preserving metadata.

7. **LangGraph Integration Smooth**: LangGraph's `StateGraph` accepts TypedDict directly with zero friction. The `total=False` pattern enables clean partial updates.

### Verification Results

All verification tests passed successfully:

```
✓ State creation works
✓ AgentOutput validation works
✓ JSON serialization works (60 bytes for minimal state)
✓ LangGraph integration works (StateGraph created successfully)
✓ 29/29 unit tests passed (100% success rate)
```

**Test Execution Time**: 0.09s for all 29 tests

### Next Steps

With ADR-012 implemented, the following can now proceed **in parallel**:

1. **ADR-013: Database Schema** - SQLAlchemy models aligned with state schema
2. **ADR-014: API Endpoints** - FastAPI routes that work with state
3. **ADR-015: Agent Prompt Engineering** - Agent implementations using state
4. **ADR-016: Orchestrator Logic** - LangGraph workflow with routing

Each agent implementation can now:
- Import state types from `src.agents`
- Use `initialize_state()` to create fresh state
- Use `update_state_with_agent_output()` to update state
- Follow patterns documented in `state_usage.md`

### Related Files

- **`src/agents/state.py`** - State definitions (366 lines)
- **`src/agents/state_utils.py`** - State utilities (376 lines)
- **`tests/unit/test_state.py`** - Unit tests (503 lines, 29 tests)
- **`docs/examples/state_usage.md`** - Usage examples (548 lines)
- **`src/agents/__init__.py`** - Module exports (101 lines)
- **`docs/decisions/README.md`** - Updated index

**Total Lines of Code**: ~1,900 lines across 6 files

---

*Date: 2026-01-08*
*Supersedes: None*
