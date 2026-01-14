"""
FastAPI application for Family Scheduler.

Implements ADR-014: API Endpoint Design & FastAPI Structure.

This is the main entry point for the HTTP API, providing:
- Event management endpoints (create, confirm, list)
- Natural language query endpoint
- Health and status endpoints
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import JSONResponse

from src.api.models import (
    CreateEventRequest,
    ConfirmEventRequest,
    ClarifyEventRequest,
    QueryRequest,
    WorkflowResponse,
    HealthResponse,
    EventListResponse,
    EventDetailResponse,
    DeleteEventResponse,
    ErrorResponse,
)
from src.api.response_builder import build_response, build_error_response
from src.api.dependencies import (
    get_orchestrator,
    init_orchestrator,
    resolve_user_id,
)
from src.api.middleware import RequestLoggingMiddleware
from src.api.auth_routes import router as auth_router
from src.orchestrator import initialize_state, invoke_orchestrator

logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Family Scheduler API")
    init_orchestrator()
    logger.info("Family Scheduler API started")

    yield

    # Shutdown
    logger.info("Shutting down Family Scheduler API")


# =============================================================================
# FastAPI Application
# =============================================================================


app = FastAPI(
    title="Family Scheduler API",
    description="""
# Family Scheduler API

Agent-based family event scheduling system using natural language.

## Core Workflows

### Event Creation
1. **POST /events** - Submit natural language request
2. System processes through specialized agents:
   - NL Parser: Extract structured data
   - Scheduling: Find optimal times
   - Resource Manager: Check availability
   - Conflict Detection: Identify issues
   - Resolution: Propose solutions (if conflicts)
3. Returns proposed event (auto-confirmed if no conflicts)
4. If conflicts: **POST /events/{event_id}/confirm** to finalize

### Natural Language Queries
- **POST /query** - Ask questions about availability, events, schedule

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
- **422** - Validation error
- **500** - Server error (agent failure)
- **503** - Service unavailable
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(auth_router)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_type": "http_error",
            "message": exc.detail,
            "retryable": exc.status_code >= 500,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_type": "internal_error",
            "message": "An unexpected error occurred",
            "retryable": True,
        },
    )


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health_check():
    """
    Check API health status.

    Returns:
        Health status including orchestrator and database status
    """
    try:
        orchestrator = get_orchestrator()
        orchestrator_ready = orchestrator is not None
    except Exception:
        orchestrator_ready = False

    # TODO: Add actual database connection check
    database_connected = True

    return HealthResponse(
        status="healthy" if orchestrator_ready else "unhealthy",
        version="0.1.0",
        orchestrator_ready=orchestrator_ready,
        database_connected=database_connected,
    )


# =============================================================================
# Event Endpoints
# =============================================================================


@app.post(
    "/events",
    response_model=WorkflowResponse,
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
- **200 with clarification_needed=true**: Need more information
- **500**: Agent workflow failed
    """,
    responses={
        200: {"description": "Event created (proposed or confirmed)"},
        422: {"description": "Validation error"},
        500: {"description": "Agent execution failed"},
        503: {"description": "Service unavailable"},
    },
    tags=["Events"],
)
async def create_event(
    request: CreateEventRequest,
    x_user_id: Optional[str] = Header(None),
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    """
    Create event from natural language.

    Invokes the orchestrator to process the natural language request
    through specialized agents.
    """
    user_id = resolve_user_id(request.user_id, x_user_id)

    logger.info(f"Creating event for user {user_id}: '{request.message[:50]}...'")

    try:
        # Initialize state and invoke orchestrator
        state = initialize_state(
            user_input=request.message,
            user_id=user_id,
            conversation_id=request.conversation_id,
        )

        final_state = invoke_orchestrator(
            graph=orchestrator,
            user_input=request.message,
            user_id=user_id,
            conversation_id=request.conversation_id,
        )

        return build_response(final_state)

    except Exception as e:
        logger.error(f"Failed to create event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent workflow failed: {str(e)}",
        )


@app.post(
    "/events/{event_id}/confirm",
    response_model=WorkflowResponse,
    summary="Confirm proposed event",
    description="""
Confirm a proposed event, optionally applying a resolution strategy.

This endpoint is used after event creation when conflicts were detected.
Select one of the `proposed_resolutions` from the creation response.

## Idempotency
Confirming an already-confirmed event returns success without changes.
    """,
    responses={
        200: {"description": "Event confirmed"},
        404: {"description": "Event not found"},
        500: {"description": "Confirmation failed"},
    },
    tags=["Events"],
)
async def confirm_event(
    event_id: str,
    request: ConfirmEventRequest,
    x_user_id: Optional[str] = Header(None),
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    """
    Confirm proposed event with optional resolution.

    Applies the selected resolution strategy and confirms the event.
    """
    user_id = x_user_id or "default_user"

    logger.info(f"Confirming event {event_id} with resolution {request.resolution_id}")

    # TODO: Load event from database and check status
    # For now, return a mock successful confirmation

    # Create confirmation response
    from src.api.models import WorkflowResult

    return WorkflowResponse(
        workflow_id=event_id,
        status="completed",
        result=WorkflowResult(
            event={
                "id": event_id,
                "status": "confirmed",
            },
            auto_confirmed=True,
        ),
        explanation="Event confirmed successfully",
        workflow_steps=["confirmation"],
    )


@app.get(
    "/events",
    response_model=EventListResponse,
    summary="List events",
    description="List events from user's Google Calendar with optional filtering by date.",
    tags=["Events"],
)
async def list_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO 8601)"),
    x_user_id: Optional[str] = Header(None, description="User ID for calendar access"),
) -> EventListResponse:
    """
    List events from user's Google Calendar.

    Requires user to have completed OAuth authorization.
    Default date range is today to 30 days from now.
    """
    from datetime import datetime, timedelta, timezone
    from dateutil.parser import parse as parse_date
    from src.services.calendar_service import get_user_calendar_service

    user_id = x_user_id or "default_user"

    # Get user's calendar service
    calendar_service = await get_user_calendar_service(user_id)
    if calendar_service is None:
        raise HTTPException(
            status_code=401,
            detail="Calendar not connected. Please authorize via /auth/google/login"
        )

    # Parse date range (default: today to 30 days from now)
    now = datetime.now(timezone.utc)
    try:
        start = parse_date(start_date) if start_date else now
        end = parse_date(end_date) if end_date else now + timedelta(days=30)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    # Ensure timezone aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    try:
        # Query calendar
        events = calendar_service.get_events_in_range(start, end)

        # Convert to response format
        event_list = []
        for event in events:
            event_list.append({
                "id": event.id,
                "title": event.title,
                "description": event.description,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "location": event.location,
                "all_day": event.all_day,
                "status": event.status,
                "calendar_id": event.calendar_id,
            })

        # Apply pagination
        total = len(event_list)
        paginated = event_list[offset:offset + limit]

        return EventListResponse(
            events=paginated,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(f"Failed to list events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")


@app.get(
    "/events/{event_id}",
    response_model=EventDetailResponse,
    summary="Get event details",
    description="Get detailed information about a specific event from user's Google Calendar.",
    tags=["Events"],
)
async def get_event(
    event_id: str,
    x_user_id: Optional[str] = Header(None, description="User ID for calendar access"),
) -> EventDetailResponse:
    """
    Get event details by ID from user's Google Calendar.

    Requires user to have completed OAuth authorization.
    """
    from src.services.calendar_service import get_user_calendar_service

    user_id = x_user_id or "default_user"

    # Get user's calendar service
    calendar_service = await get_user_calendar_service(user_id)
    if calendar_service is None:
        raise HTTPException(
            status_code=401,
            detail="Calendar not connected. Please authorize via /auth/google/login"
        )

    try:
        # Fetch event from calendar
        event = calendar_service.get_event_by_id(event_id)

        if event is None:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        # Extract optional metadata fields
        created_at = event.metadata.get('created') if event.metadata else None
        updated_at = event.metadata.get('updated') if event.metadata else None
        html_link = event.metadata.get('htmlLink') if event.metadata else None

        return EventDetailResponse(
            id=event.id,
            title=event.title,
            description=event.description,
            start_time=event.start_time.isoformat() if event.start_time else "",
            end_time=event.end_time.isoformat() if event.end_time else "",
            location=event.location,
            all_day=event.all_day,
            status=event.status,
            calendar_id=event.calendar_id,
            html_link=html_link,
            created_at=created_at,
            updated_at=updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch event: {str(e)}")


@app.delete(
    "/events/{event_id}",
    response_model=DeleteEventResponse,
    summary="Delete event",
    description="Delete an event from user's Google Calendar.",
    tags=["Events"],
)
async def delete_event(
    event_id: str,
    x_user_id: Optional[str] = Header(None, description="User ID for calendar access"),
) -> DeleteEventResponse:
    """
    Delete an event from user's Google Calendar.

    Requires user to have completed OAuth authorization.
    """
    from src.services.calendar_service import get_user_calendar_service

    user_id = x_user_id or "default_user"

    # Get user's calendar service
    calendar_service = await get_user_calendar_service(user_id)
    if calendar_service is None:
        raise HTTPException(
            status_code=401,
            detail="Calendar not connected. Please authorize via /auth/google/login"
        )

    try:
        # Delete event from calendar
        deleted = calendar_service.delete_event(event_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        logger.info(f"Deleted event {event_id} for user {user_id}")

        return DeleteEventResponse(
            success=True,
            event_id=event_id,
            message="Event deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")


# =============================================================================
# Clarification Endpoint
# =============================================================================


@app.post(
    "/events/clarify",
    response_model=WorkflowResponse,
    summary="Clarify event request",
    description="""
Provide additional context for a low-confidence event parsing.

Use this endpoint when the initial event creation returned
`clarification_needed=true` in the response.
    """,
    tags=["Events"],
)
async def clarify_event(
    request: ClarifyEventRequest,
    x_user_id: Optional[str] = Header(None),
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    """
    Clarify event with additional context.

    Re-runs the orchestrator with original message plus clarification.
    """
    user_id = request.user_id or x_user_id or "default_user"

    logger.info(f"Clarifying event {request.event_id}: '{request.clarification[:50]}...'")

    # TODO: Load original event message and combine with clarification
    # For now, just process the clarification as a new request

    try:
        final_state = invoke_orchestrator(
            graph=orchestrator,
            user_input=request.clarification,
            user_id=user_id,
        )

        return build_response(final_state)

    except Exception as e:
        logger.error(f"Failed to clarify event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Clarification failed: {str(e)}",
        )


# =============================================================================
# Query Endpoint
# =============================================================================


@app.post(
    "/query",
    response_model=WorkflowResponse,
    summary="Natural language query",
    description="""
Ask questions about your schedule using natural language.

## Example Queries
- "When is everyone free next Saturday?"
- "What events do I have this week?"
- "Is the car available tomorrow afternoon?"
- "Who is attending the team meeting?"

The Query Agent will interpret your question and provide a natural language response.
    """,
    tags=["Query"],
)
async def query_schedule(
    request: QueryRequest,
    x_user_id: Optional[str] = Header(None),
    orchestrator=Depends(get_orchestrator),
) -> WorkflowResponse:
    """
    Answer natural language queries about schedule.

    Routes the query through the orchestrator to the Query Agent.
    """
    user_id = request.user_id or x_user_id or "default_user"

    logger.info(f"Processing query for user {user_id}: '{request.message[:50]}...'")

    try:
        final_state = invoke_orchestrator(
            graph=orchestrator,
            user_input=request.message,
            user_id=user_id,
        )

        return build_response(final_state)

    except Exception as e:
        logger.error(f"Failed to process query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}",
        )


# =============================================================================
# Run with Uvicorn
# =============================================================================


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the API server with Uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server(reload=True)
