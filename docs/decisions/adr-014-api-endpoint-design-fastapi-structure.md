# ADR-014: API Endpoint Design & FastAPI Structure

## Status
Accepted

**Implementation Status**: Not yet implemented
**Implementation Date**: TBD

## Context

The Family Scheduler requires an HTTP API layer to expose the LangGraph orchestrator's agent workflows to users. The API must translate between HTTP request/response semantics and the state-based agent orchestration system, while supporting the proposal flow for event creation (ADR-003) and maintaining the hybrid output format (ADR-004).

### Current State

**What Exists:**
- FastAPI 0.109.0 and Uvicorn installed
- Pydantic 2.5.0 for request/response validation
- LangGraph orchestrator architecture defined (ADR-002)
- State schema fully implemented (ADR-012)
- Database schema designed (ADR-013)
- Proposal flow documented (ADR-003)
- Hybrid agent output format specified (ADR-004)

**What Needs Decision:**
- Synchronous vs asynchronous response handling
- Endpoint structure and REST design
- Orchestrator invocation pattern
- Response format and error handling
- Conflict resolution workflow
- Authentication and user context (Phase 1)
- Logging and monitoring strategy
- OpenAPI documentation approach

### Requirements

**Functional Requirements:**
1. Support event creation from natural language input
2. Implement two-phase commit for conflict resolution (ADR-003)
3. Expose agent outputs with explanations (ADR-004)
4. Enable natural language queries about schedule
5. Provide event listing, detail, and modification endpoints
6. Support resource and family member management

**Non-Functional Requirements:**
1. **Response Time**: < 5 seconds (p95) for event creation
2. **Timeout**: Support workflows up to 120 seconds
3. **Transparency**: Expose agent reasoning and confidence
4. **Error Handling**: Distinguish conflicts from errors
5. **Documentation**: Auto-generated OpenAPI/Swagger docs

**Integration Requirements:**
1. Invoke LangGraph orchestrator with state (ADR-012)
2. Query database through agents (ADR-013)
3. Maintain audit trail of workflow execution
4. Support multi-turn conversations with context

**Phase Constraints:**
- Phase 1: Synchronous execution, single-user focus, local SQLite
- Phase 2: Async task queue, multi-user, cloud deployment

## Decision

We will implement a **synchronous FastAPI application** with the following architectural decisions:

### 1. Synchronous Response Handling (Phase 1)

**Decision:** Use synchronous endpoint execution with 120-second timeout.

**Rationale:**
- Simple, learning-focused approach appropriate for Phase 1
- Single-user context doesn't require complex async architecture
- 120s timeout sufficient for multi-agent workflows (6 agents × ~500ms each + database queries)
- Natural migration path to async in Phase 2

**Implementation:**
```python
@app.post("/events")
async def create_event(
    request: CreateEventRequest,
    orchestrator = Depends(get_orchestrator)
) -> WorkflowResponse:
    """
    Create event - blocks until orchestrator completes.
    Timeout: 120 seconds
    """
    state = initialize_state(
        user_input=request.message,
        user_id=request.user_id or "default_user"
    )

    final_state = orchestrator.invoke(state)  # Blocks until complete
    return build_response(final_state)
```

**Phase 2 Migration Path:**
```python
# Future: Async task queue pattern
POST /events → Returns task_id
GET /tasks/{task_id} → Poll for status
```

**Timeout Configuration:**
- FastAPI request timeout: 120 seconds
- Orchestrator execution limit: 60 seconds
- Individual agent timeout: 30 seconds
- LLM API timeout: 30 seconds

---

### 2. Endpoint Structure & REST Design

**Decision:** Resource-oriented REST endpoints with special workflow endpoints.

**Endpoint Structure:**

```
# Event Management (Primary Workflows)
POST   /events                    - Create event from natural language
GET    /events                    - List events with filters
GET    /events/{event_id}         - Get event details
POST   /events/{event_id}/confirm - Confirm proposed event
POST   /events/{event_id}/cancel  - Cancel event
DELETE /events/{event_id}         - Soft delete event

# Clarification (Low Confidence)
POST   /events/clarify            - Provide additional context

# Natural Language Queries
POST   /query                     - Ask questions about schedule

# Family & Members (CRUD)
GET    /families/{family_id}      - Get family info
GET    /families/{family_id}/members - List members
POST   /families/{family_id}/members - Add member

# Resources (CRUD)
GET    /resources                 - List resources
POST   /resources                 - Create resource
GET    /resources/{resource_id}   - Get resource details
PUT    /resources/{resource_id}   - Update resource

# Health & Status
GET    /health                    - API health check
GET    /status                    - Orchestrator status
```

**Design Principles:**
1. **POST /events is primary entry point** - Accepts natural language, returns proposed or confirmed event
2. **Two-phase commit** - Separate confirmation endpoint for conflict resolution
3. **Non-RESTful query endpoint** - POST /query for natural language questions
4. **Consistent response format** - All orchestrator workflows return WorkflowResponse

**Pagination:**
- GET /events supports query params: `?limit=50&offset=0&start_date=2026-01-01`
- Use limit/offset pattern for Phase 1 simplicity

---

### 3. Orchestrator Invocation Pattern

**Decision:** Thin API wrapper using dependency injection.

**Pattern:**

```python
from fastapi import FastAPI, Depends, HTTPException
from src.agents.state import initialize_state, FamilySchedulerState
from src.orchestrator import build_orchestrator_graph

app = FastAPI(...)

# Global orchestrator (singleton initialized at startup)
orchestrator_graph = None

@app.on_event("startup")
async def startup():
    """Initialize orchestrator once at startup."""
    global orchestrator_graph
    orchestrator_graph = build_orchestrator_graph()
    logger.info("Orchestrator initialized")

async def get_orchestrator():
    """Dependency injection for orchestrator."""
    if orchestrator_graph is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return orchestrator_graph

@app.post("/events", response_model=WorkflowResponse)
async def create_event(
    request: CreateEventRequest,
    orchestrator = Depends(get_orchestrator)
) -> WorkflowResponse:
    """
    Create event from natural language.

    1. Initialize state with user input
    2. Invoke orchestrator (blocks until complete)
    3. Extract and format response
    """
    # 1. Initialize state
    state = initialize_state(
        user_input=request.message,
        user_id=request.user_id or "default_user"
    )

    # 2. Invoke orchestrator
    try:
        final_state = orchestrator.invoke(
            state,
            config={"configurable": {"thread_id": state["conversation_id"]}}
        )
    except Exception as e:
        logger.error(f"Orchestrator failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Agent workflow failed"
        )

    # 3. Extract response
    return build_response(final_state)
```

**Response Builder:**

```python
def build_response(state: FamilySchedulerState) -> WorkflowResponse:
    """Extract WorkflowResponse from final state."""
    return WorkflowResponse(
        workflow_id=state["conversation_id"],
        status=state["workflow_status"],
        result=extract_result(state),
        explanation=build_explanation(state),
        agent_outputs=state.get("agent_outputs", {}),
        workflow_steps=extract_steps(state.get("audit_log", []))
    )

def extract_result(state: FamilySchedulerState) -> dict:
    """Extract primary result data from state."""
    proposed_event = state.get("proposed_event")
    conflicts = state.get("detected_conflicts", {})

    return {
        "event": proposed_event,
        "conflicts": conflicts.get("conflicts", []),
        "proposed_resolutions": conflicts.get("proposed_resolutions", []),
        "auto_confirmed": not conflicts.get("has_conflicts", False)
    }

def build_explanation(state: FamilySchedulerState) -> str:
    """Build user-friendly explanation from audit log."""
    explanations = []
    for entry in state.get("audit_log", []):
        if "explanation" in entry:
            explanations.append(entry["explanation"])

    # Add final status message
    if state.get("workflow_status") == "completed":
        explanations.append("Event created successfully")
    elif state.get("detected_conflicts", {}).get("has_conflicts"):
        explanations.append("Conflicts detected - review options above")

    return " → ".join(explanations)
```

**Key Principles:**
- API is thin wrapper - no business logic
- State flows through orchestrator unchanged
- Response builder extracts relevant data
- Orchestrator singleton initialized once
- Dependency injection for testability

---

### 4. Response Format: WorkflowResponse Envelope

**Decision:** Standard response envelope for all orchestrator-driven endpoints.

**Schema:**

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class WorkflowResponse(BaseModel):
    """Standard response envelope for orchestrator workflows."""

    # Workflow identification
    workflow_id: str = Field(
        ...,
        description="Conversation ID for tracking and multi-turn context"
    )

    status: Literal["completed", "awaiting_user", "failed"] = Field(
        ...,
        description="Workflow completion status"
    )

    # Primary result data
    result: dict = Field(
        ...,
        description="Main workflow output (event, conflicts, query answer, etc.)"
    )

    # User-facing explanation
    explanation: str = Field(
        ...,
        description="Human-readable summary of what happened"
    )

    # Transparency and debugging (always included)
    agent_outputs: dict[str, dict] = Field(
        default_factory=dict,
        description="Full outputs from all agents (data, confidence, reasoning)"
    )

    workflow_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of workflow steps executed"
    )

    # Errors (if any)
    errors: Optional[list[dict]] = Field(
        None,
        description="Error details if workflow failed"
    )
```

**Example Responses:**

```json
// Success - Auto-confirmed
{
    "workflow_id": "conv_abc123",
    "status": "completed",
    "result": {
        "event": {
            "id": "event_123",
            "title": "Soccer practice",
            "start_time": "2026-01-11T14:00:00Z",
            "end_time": "2026-01-11T16:00:00Z",
            "status": "confirmed"
        },
        "conflicts": [],
        "proposed_resolutions": [],
        "auto_confirmed": true
    },
    "explanation": "Parsed as soccer practice Saturday 2pm → Scheduled → No conflicts → Event created!",
    "agent_outputs": {
        "nl_parser": {
            "data": {...},
            "confidence": 0.95,
            "explanation": "Understood as new event creation",
            "reasoning": "Clear time reference and participants"
        },
        "scheduling": {...},
        "conflict_detection": {...}
    },
    "workflow_steps": ["nl_parsing", "scheduling", "resource_manager", "conflict_detection", "auto_confirm"]
}

// Awaiting User - Conflicts
{
    "workflow_id": "conv_def456",
    "status": "awaiting_user",
    "result": {
        "event": {
            "id": "event_456",
            "status": "proposed",
            ...
        },
        "conflicts": [
            {
                "id": "conflict_789",
                "type": "time_conflict",
                "severity": "high",
                "conflicting_event_title": "Dentist Appointment",
                "description": "Overlaps 2:30pm-3:30pm"
            }
        ],
        "proposed_resolutions": [
            {
                "resolution_id": "res_1",
                "strategy": "move_event",
                "description": "Move soccer to 4pm-6pm",
                "score": 0.90
            }
        ],
        "auto_confirmed": false
    },
    "explanation": "Event proposed but conflicts detected → Choose a resolution",
    "agent_outputs": {...},
    "workflow_steps": ["nl_parsing", "scheduling", "conflict_detection", "resolution"]
}
```

**Rationale:**
- **agent_outputs always included** - Transparency for debugging, no optional toggle
- **workflow_steps** - Shows what orchestrator did
- **explanation** - User-friendly summary from audit log
- Follows ADR-004 hybrid format (structured + natural language)

---

### 5. Error Handling & Classification

**Decision:** Distinguish workflow outcomes (conflicts) from actual errors.

**Error Taxonomy:**

```python
class ErrorResponse(BaseModel):
    """Error information for failed workflows."""
    error_type: Literal[
        "validation_error",      # Bad request format (400)
        "low_confidence",        # Agent needs clarification (200)
        "agent_failure",         # Agent crashed (500)
        "database_error",        # DB query failed (500)
        "llm_error",            # LLM API error (500/503)
        "timeout_error",        # Exceeded time limit (500)
        "conflict_unresolvable"  # No acceptable resolution (200)
    ]
    message: str
    details: Optional[dict] = None
    retryable: bool
```

**Classification:**

**NOT ERRORS (Return 200):**
1. **Conflicts detected** - Normal workflow outcome, present resolutions
2. **Low confidence** - Request clarification, workflow succeeded
3. **Soft constraint violations** - Warnings in result

**ACTUAL ERRORS:**
1. **400 Bad Request** - Invalid input (bad date format, missing field)
2. **422 Unprocessable Entity** - Pydantic validation failed
3. **500 Internal Server Error** - Agent crashed, DB error, LLM failed
4. **503 Service Unavailable** - LLM API down

**HTTP Status Code Map:**

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success (including conflicts) | Event proposed with conflicts |
| 400 | Invalid request | Malformed date, missing field |
| 404 | Not found | Event ID doesn't exist |
| 422 | Validation error | Invalid enum value |
| 500 | Server error | Agent crashed, DB error |
| 503 | Service unavailable | LLM API down |

**Example Error Response:**

```python
# Low confidence (200 OK - not an error, needs clarification)
{
    "workflow_id": "conv_ghi789",
    "status": "awaiting_user",
    "result": {
        "clarification_needed": true,
        "ambiguous_fields": ["date"],
        "agent_reasoning": "Multiple interpretations: 'next Saturday' could mean Jan 18 or Jan 25"
    },
    "explanation": "Could you clarify which Saturday you meant?",
    "agent_outputs": {...}
}

# Actual Error (500 Internal Server Error)
{
    "error_type": "agent_failure",
    "message": "NL Parser agent failed to execute",
    "details": {
        "agent": "nl_parser",
        "exception": "TimeoutError",
        "error_message": "LLM request exceeded 30s timeout"
    },
    "retryable": true
}
```

**Stack Trace Policy:**
- **Development**: Include stack traces in error details
- **Production**: Omit stack traces, log internally only

**Rationale:**
- **Conflicts are features** - Return 200 to indicate successful workflow
- Low confidence returns 200 - Agent did its job (requested clarification)
- Clear separation helps clients handle different scenarios

---

### 6. Conflict Resolution Workflow

**Decision:** Two-phase commit with POST /events/{id}/confirm.

**Workflow:**

```
┌────────────────────────────────────────────────────────┐
│ Phase 1: Proposal                                      │
├────────────────────────────────────────────────────────┤
│ POST /events                                           │
│ Body: {"message": "Schedule soccer Saturday at 2pm"}  │
│                                                        │
│ ↓ Orchestrator runs                                   │
│                                                        │
│ Response 200 (awaiting_user):                         │
│ {                                                      │
│   "status": "awaiting_user",                          │
│   "result": {                                         │
│     "event": {id: "evt_123", status: "proposed"},    │
│     "conflicts": [...],                               │
│     "proposed_resolutions": [                         │
│       {id: "res_1", strategy: "move_event", ...},    │
│       {id: "res_2", strategy: "cancel_conflicting"}  │
│     ]                                                 │
│   }                                                   │
│ }                                                     │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ User Reviews in UI                                     │
│ - Sees conflicts                                       │
│ - Reviews proposed resolutions                         │
│ - Selects resolution or cancels                        │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Phase 2: Confirmation                                  │
├────────────────────────────────────────────────────────┤
│ POST /events/evt_123/confirm                          │
│ Body: {"resolution_id": "res_1"}                      │
│                                                        │
│ ↓ Apply resolution, update event                      │
│                                                        │
│ Response 200 (completed):                             │
│ {                                                      │
│   "status": "completed",                              │
│   "result": {                                         │
│     "event": {                                        │
│       id: "evt_123",                                  │
│       status: "confirmed",                            │
│       start_time: "2026-01-11T16:00:00Z"  # Moved    │
│     }                                                 │
│   },                                                  │
│   "explanation": "Event confirmed. Moved to 4pm."    │
│ }                                                     │
└────────────────────────────────────────────────────────┘
```

**Confirmation Endpoint:**

```python
@app.post("/events/{event_id}/confirm")
async def confirm_event(
    event_id: str,
    request: ConfirmEventRequest,
    orchestrator = Depends(get_orchestrator)
) -> WorkflowResponse:
    """
    Confirm proposed event, optionally applying a resolution.

    Idempotent: Confirming already-confirmed event returns success.
    """
    # Load event
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Idempotency: Already confirmed
    if event.status == "confirmed":
        return WorkflowResponse(
            workflow_id=event_id,
            status="completed",
            result={"event": event.to_dict()},
            explanation="Event already confirmed"
        )

    # Invoke orchestrator to apply resolution
    state = initialize_confirmation_state(
        event_id=event_id,
        resolution_id=request.resolution_id
    )

    final_state = orchestrator.invoke(state)
    return build_response(final_state)
```

**Idempotency:** Confirmation is idempotent - confirming confirmed event returns success without error.

**Clarification Flow (Low Confidence):**

```python
@app.post("/events/clarify")
async def clarify_event(
    request: ClarifyEventRequest,
    orchestrator = Depends(get_orchestrator)
) -> WorkflowResponse:
    """
    Provide additional context for low-confidence parsing.

    Re-runs orchestrator with original message + clarification.
    """
    original_event = get_event(request.event_id)

    state = initialize_state(
        user_input=f"{original_event.original_message}. {request.clarification}",
        user_id=request.user_id
    )

    final_state = orchestrator.invoke(state)
    return build_response(final_state)
```

---

### 7. Request Validation with Pydantic

**Decision:** Strong typing with Pydantic models for all requests/responses.

**Core Request Models:**

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class CreateEventRequest(BaseModel):
    """Request to create event from natural language."""
    message: str = Field(
        ...,
        description="Natural language event description",
        min_length=3,
        max_length=500,
        examples=["Schedule soccer practice Saturday at 2pm"]
    )
    user_id: Optional[str] = Field(
        None,
        description="User making request (defaults to default_user)"
    )
    family_id: Optional[str] = Field(
        None,
        description="Family context for event"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Continue previous conversation (multi-turn)"
    )

    @field_validator('message')
    @classmethod
    def validate_message_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()

class ConfirmEventRequest(BaseModel):
    """Request to confirm proposed event."""
    resolution_id: Optional[str] = Field(
        None,
        description="Resolution strategy to apply (if conflicts)"
    )
    user_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="User's reason for confirming"
    )

class ClarifyEventRequest(BaseModel):
    """Request to clarify low-confidence parsing."""
    event_id: str = Field(..., description="Event ID to clarify")
    clarification: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Additional context"
    )
    user_id: Optional[str] = None

class QueryRequest(BaseModel):
    """Natural language query about schedule."""
    message: str = Field(
        ...,
        min_length=3,
        max_length=500,
        examples=["When is everyone free next Saturday?"]
    )
    user_id: Optional[str] = None
    family_id: Optional[str] = None
```

**Benefits:**
- Automatic validation before orchestrator invocation
- Auto-generated OpenAPI schema
- Type hints for IDE support
- Clear documentation in /docs

**Conversation Threading:**
- Client can include `conversation_id` to continue multi-turn conversation
- Orchestrator uses thread_id for LangGraph checkpointing
- Enables context from previous messages

---

### 8. Authentication & User Context (Phase 1)

**Decision:** Header-based user identification with default fallback (Phase 1).

**Phase 1 Implementation:**

```python
from fastapi import Header

@app.post("/events")
async def create_event(
    request: CreateEventRequest,
    x_user_id: Optional[str] = Header(None),
    x_family_id: Optional[str] = Header(None)
):
    """
    Extract user from request body, header, or default.
    Priority: request.user_id > X-User-ID header > "default_user"
    """
    user_id = request.user_id or x_user_id or "default_user"
    family_id = request.family_id or x_family_id or "default_family"

    # No validation - trust headers for Phase 1
    state = initialize_state(
        user_input=request.message,
        user_id=user_id
    )
    ...
```

**Request Example:**

```http
POST /events HTTP/1.1
Host: localhost:8000
Content-Type: application/json
X-User-ID: parent_1
X-Family-ID: family_123

{
  "message": "Schedule soccer Saturday at 2pm"
}
```

**Phase 2 (Planned):**
- JWT tokens or OAuth 2.0
- User authentication service
- Validate user_id exists in database
- Permission model (who can create/modify events)

**Rationale:**
- Phase 1: Single developer/family, no security needed
- Headers provide flexibility without requiring body changes
- Easy migration to JWT (replace header extraction)

---

### 9. Logging & Monitoring

**Decision:** Request ID tracking with middleware, structured logging optional.

**Implementation:**

```python
import logging
from contextvars import ContextVar
import time
import uuid

# Context variable for request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger("family_scheduler.api")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing and request ID."""
    req_id = str(uuid.uuid4())
    request_id_ctx.set(req_id)

    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={"request_id": req_id, "method": request.method, "path": request.url.path}
    )

    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start

    logger.info(
        f"Response: {response.status_code} in {elapsed:.2f}s",
        extra={
            "request_id": req_id,
            "status_code": response.status_code,
            "elapsed_ms": elapsed * 1000
        }
    )

    # Include request ID in response header
    response.headers["X-Request-ID"] = req_id
    return response

@app.exception_handler(Exception)
async def log_exceptions(request: Request, exc: Exception):
    """Log all unhandled exceptions."""
    req_id = request_id_ctx.get()
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"request_id": req_id},
        exc_info=True
    )
    raise
```

**Metrics to Track:**
- Request count by endpoint
- Response time (p50, p95, p99)
- Error rate by error_type
- Agent execution time (from audit_log)
- LLM token usage (from agent outputs)

**Logging Format:**
- **Phase 1**: Plain text logs with extra fields
- **Phase 2**: Structured JSON logs for log aggregation

**Rationale:**
- Request ID enables tracing through orchestrator and agents
- Context variables work across async calls
- Plain text sufficient for local development

---

### 10. OpenAPI/Swagger Documentation

**Decision:** Comprehensive auto-generated documentation with examples.

**FastAPI Configuration:**

```python
from fastapi import FastAPI

app = FastAPI(
    title="Family Scheduler API",
    description="""
# Family Scheduler API

Agent-based family event scheduling system using natural language.

## Core Workflows

### Event Creation
1. **POST /events** - Submit natural language request
2. System processes through 6 specialized agents:
   - NL Parser: Extract structured data
   - Scheduling: Find optimal times
   - Resource Manager: Check availability
   - Conflict Detection: Identify issues
   - Resolution: Propose solutions
3. Returns proposed event (auto-confirmed if no conflicts)
4. If conflicts: **POST /events/{id}/confirm** to finalize

### Natural Language Queries
- **POST /query** - Ask questions about availability, events, schedule

## Agent Architecture

Uses LangGraph orchestrator coordinating specialized agents:
- **NL Parser** - Natural language understanding
- **Scheduling Agent** - Time optimization
- **Resource Manager** - Capacity checking
- **Conflict Detection** - Issue identification
- **Resolution Agent** - Solution generation
- **Query Agent** - Question answering

## Response Format

All orchestrator endpoints return `WorkflowResponse`:
- `result` - Primary output (event, conflicts, etc.)
- `explanation` - Human-readable summary
- `agent_outputs` - Full agent reasoning (transparency)
- `workflow_steps` - Audit trail of execution

## Error Handling

**Conflicts are not errors** - Conflicts return 200 with resolution options.

- **200** - Success (including conflicts needing resolution)
- **400** - Invalid request format
- **404** - Resource not found
- **500** - Server error (agent failure, database error)
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Family Scheduler Team",
        "email": "support@familyscheduler.local"
    },
    license_info={
        "name": "MIT"
    }
)

@app.post(
    "/events",
    summary="Create event from natural language",
    description="""
Create a new event by providing natural language input.

## Workflow Steps
1. NL Parser extracts structured event data
2. Scheduling Agent finds optimal time slot
3. Resource Manager checks resource availability
4. Conflict Detection identifies scheduling conflicts
5. If conflicts: Resolution Agent proposes solutions
6. Auto-confirm if no conflicts

## Response Behavior
- **200 with auto_confirmed=true**: Event created and confirmed
- **200 with auto_confirmed=false**: Event proposed, conflicts detected
  - Review `proposed_resolutions` in response
  - Call `POST /events/{event_id}/confirm` to finalize
- **400**: Invalid request format
- **500**: Agent workflow failed

## Examples

### No Conflicts
```json
{
  "message": "Schedule soccer practice Saturday at 2pm"
}
```
Returns: Event confirmed immediately

### With Conflicts
```json
{
  "message": "Schedule dentist Saturday at 2pm"
}
```
Returns: Proposed event + conflicts + resolution options
    """,
    response_model=WorkflowResponse,
    responses={
        200: {
            "description": "Event created (proposed or confirmed)",
            "content": {
                "application/json": {
                    "example": {
                        "workflow_id": "conv_abc123",
                        "status": "completed",
                        "result": {
                            "event": {
                                "id": "event_123",
                                "title": "Soccer practice",
                                "status": "confirmed"
                            },
                            "auto_confirmed": True
                        },
                        "explanation": "Event created successfully",
                        "workflow_steps": ["nl_parsing", "scheduling", "conflict_detection", "auto_confirm"]
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid date format"
                    }
                }
            }
        },
        500: {"description": "Agent execution failed"}
    },
    tags=["Events"]
)
async def create_event(request: CreateEventRequest) -> WorkflowResponse:
    ...
```

**Benefits:**
- Auto-generated interactive docs at http://localhost:8000/docs
- ReDoc alternative at http://localhost:8000/redoc
- OpenAPI schema at http://localhost:8000/openapi.json
- Client SDK generation support
- Clear examples and workflow documentation

---

## Consequences

### Positive

1. **Simple Implementation**: Synchronous approach reduces complexity for Phase 1
2. **Transparent**: WorkflowResponse exposes agent reasoning and confidence
3. **Clear Semantics**: Conflicts return 200 (not errors), consistent with proposal flow
4. **Testable**: Thin API layer easy to test independently from orchestrator
5. **Documented**: Auto-generated OpenAPI docs provide clear API contract
6. **Flexible**: Response envelope supports various workflow types
7. **Debuggable**: Request ID tracking enables end-to-end tracing
8. **Maintainable**: Pydantic validation catches errors before orchestrator invocation

### Negative

1. **Timeout Risk**: Long-running workflows may exceed 120s (mitigated by Phase 2 async)
2. **Blocking**: Synchronous endpoints block during orchestrator execution (acceptable for Phase 1)
3. **No Streaming**: Users don't see progress during multi-agent workflows (Phase 2 feature)
4. **Response Size**: Full agent_outputs may be large (acceptable for debugging)

### Mitigations

1. **Timeout Risk**: Monitor p95 response times, add async task queue in Phase 2
2. **Blocking**: Sufficient for single-user Phase 1, plan migration documented
3. **No Streaming**: Add SSE/WebSocket in Phase 2 when needed
4. **Response Size**: Consider compression if bandwidth becomes issue

## Alternatives Considered

### Alternative 1: Asynchronous with Polling from Start

**Pros:**
- Matches Phase 2 architecture
- No timeout risk
- Better scalability

**Cons:**
- More complex for learning project
- Requires task storage
- More complex UX (polling)

**Decision:** Rejected - Premature optimization for Phase 1

### Alternative 2: Minimal Response (No agent_outputs)

**Pros:**
- Smaller responses
- Faster serialization

**Cons:**
- Loses transparency
- Harder to debug
- Doesn't support "show your work" use case

**Decision:** Rejected - Transparency more valuable than response size

### Alternative 3: Separate Endpoints for Each Agent

**Pros:**
- Direct agent access
- Flexible composition

**Cons:**
- Violates ADR-002 (hub-and-spoke)
- No orchestration
- Clients must implement workflow logic

**Decision:** Rejected - Violates architecture

### Alternative 4: WebSocket-First

**Pros:**
- Real-time updates
- Bidirectional communication
- Best UX for long workflows

**Cons:**
- Overkill for Phase 1
- More complex implementation
- Requires WebSocket client support

**Decision:** Rejected - Too complex for Phase 1, consider for Phase 2

### Alternative 5: GraphQL

**Pros:**
- Flexible queries
- Client-controlled response shape
- Modern API pattern

**Cons:**
- Overhead for learning project
- Doesn't map well to workflow patterns
- More complex than REST for this use case

**Decision:** Rejected - REST sufficient for current needs

## Implementation

### Implementation Plan

**Phase 1: Core Infrastructure**
1. Create FastAPI application skeleton (`src/api/main.py`)
2. Define Pydantic request/response models (`src/api/models.py`)
3. Implement orchestrator dependency injection
4. Add logging middleware with request ID tracking

**Phase 2: Event Endpoints**
1. Implement POST /events (create event)
2. Implement POST /events/{id}/confirm (confirm event)
3. Implement GET /events (list events)
4. Implement GET /events/{id} (get event details)

**Phase 3: Additional Endpoints**
1. Implement POST /query (natural language query)
2. Implement POST /events/clarify (low confidence clarification)
3. Implement health/status endpoints

**Phase 4: Testing & Documentation**
1. Write unit tests for request validation
2. Write integration tests for full workflows
3. Write API tests with TestClient
4. Enhance OpenAPI documentation with more examples

### Testing Strategy

**Unit Tests:**
```python
# tests/unit/test_api_models.py
def test_create_event_request_validation():
    # Valid request
    request = CreateEventRequest(message="Schedule meeting")
    assert request.message == "Schedule meeting"

    # Invalid - too short
    with pytest.raises(ValidationError):
        CreateEventRequest(message="Hi")

    # Invalid - empty after strip
    with pytest.raises(ValidationError):
        CreateEventRequest(message="   ")

def test_workflow_response_serialization():
    response = WorkflowResponse(
        workflow_id="conv_123",
        status="completed",
        result={"event": {...}},
        explanation="Event created"
    )

    json_str = response.model_dump_json()
    assert "conv_123" in json_str
```

**Integration Tests:**
```python
# tests/integration/test_api_workflows.py
from fastapi.testclient import TestClient

client = TestClient(app)

def test_create_event_success():
    """Test full workflow: create event with no conflicts."""
    response = client.post(
        "/events",
        json={"message": "Schedule soccer Saturday at 2pm"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["auto_confirmed"] is True
    assert "X-Request-ID" in response.headers

def test_create_event_with_conflicts():
    """Test workflow with conflicts requiring resolution."""
    # First create dentist appointment
    client.post("/events", json={"message": "Dentist Saturday at 2pm"})

    # Try to create conflicting event
    response = client.post(
        "/events",
        json={"message": "Soccer Saturday at 2pm"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "awaiting_user"
    assert len(data["result"]["conflicts"]) > 0
    assert data["result"]["auto_confirmed"] is False

def test_confirm_event_with_resolution():
    """Test confirmation flow with resolution."""
    # Create conflicting event
    response1 = client.post("/events", json={"message": "Soccer Saturday 2pm"})
    event_id = response1.json()["result"]["event"]["id"]
    resolution_id = response1.json()["result"]["proposed_resolutions"][0]["resolution_id"]

    # Confirm with resolution
    response2 = client.post(
        f"/events/{event_id}/confirm",
        json={"resolution_id": resolution_id}
    )

    assert response2.status_code == 200
    data = response2.json()
    assert data["status"] == "completed"

def test_idempotent_confirmation():
    """Test that confirming confirmed event is idempotent."""
    # Create and confirm event
    response1 = client.post("/events", json={"message": "Soccer Saturday 2pm"})
    event_id = response1.json()["result"]["event"]["id"]

    if not response1.json()["result"]["auto_confirmed"]:
        client.post(f"/events/{event_id}/confirm")

    # Confirm again - should be idempotent
    response2 = client.post(f"/events/{event_id}/confirm")
    assert response2.status_code == 200
```

**API Tests:**
```python
# tests/api/test_error_handling.py
def test_invalid_request_format():
    """Test 422 error for Pydantic validation failure."""
    response = client.post(
        "/events",
        json={"message": "Hi"}  # Too short
    )
    assert response.status_code == 422

def test_not_found():
    """Test 404 for non-existent event."""
    response = client.post("/events/invalid_id/confirm")
    assert response.status_code == 404

def test_agent_failure():
    """Test 500 for orchestrator failure."""
    # Mock orchestrator to raise exception
    with mock.patch("src.api.main.orchestrator_graph") as mock_orch:
        mock_orch.invoke.side_effect = Exception("Agent crashed")

        response = client.post(
            "/events",
            json={"message": "Schedule meeting"}
        )

        assert response.status_code == 500
```

### Performance Requirements

**Target Metrics (Phase 1):**
- POST /events response time: < 5s (p95)
- GET /events response time: < 500ms (p95)
- Orchestrator execution: < 4s (6 agents × ~500ms)
- Database queries: < 100ms per query

**Timeout Configuration:**
- FastAPI request timeout: 120s
- Orchestrator execution: 60s
- Individual agent: 30s
- LLM API: 30s

### Critical Files

**New Files:**
- `src/api/main.py` - FastAPI application, endpoints
- `src/api/models.py` - Pydantic request/response models
- `src/api/dependencies.py` - Dependency injection (orchestrator, DB)
- `src/api/middleware.py` - Logging, request ID tracking
- `src/api/response_builder.py` - Extract WorkflowResponse from state

**Test Files:**
- `tests/unit/test_api_models.py` - Pydantic validation tests
- `tests/integration/test_api_workflows.py` - Full workflow tests
- `tests/api/test_endpoints.py` - Endpoint behavior tests
- `tests/api/test_error_handling.py` - Error scenario tests

**Configuration:**
- `src/config.py` - Add API-specific settings (timeout, CORS)

### Related ADRs

- **ADR-002**: Hub-and-Spoke Agent Architecture - API must invoke orchestrator only
- **ADR-003**: Proposal Flow for Event Creation - Two-phase commit pattern
- **ADR-004**: Hybrid Agent Output Format - Response includes data + explanation
- **ADR-012**: LangGraph State Schema - State flows through API/orchestrator
- **ADR-013**: SQLAlchemy Database Schema - Agents query database through ORM

---

**Last Updated**: 2026-01-11
**Status**: Accepted, awaiting implementation
