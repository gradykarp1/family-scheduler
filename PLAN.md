# Implementation Plan: Family Scheduler

## Current Status

### Completed
1. **Project Architecture** - 16 ADR documents defining all system aspects
2. **Development Environment** (ADR-010, ADR-011) - Poetry, LLM providers, config management
3. **LangGraph State Schema** (ADR-012) - TypedDict state, Pydantic output models
4. **Database Models** (ADR-013) - All 8 core SQLAlchemy models with 120 tests
   - FamilyMember, Calendar, Event, EventParticipant
   - Resource, ResourceReservation, Constraint, Conflict
5. **Database Infrastructure** - Session management, GUID compatibility, soft deletion
6. **Orchestrator** (ADR-015) - LangGraph graph with 8 nodes, 50 tests
   - `src/orchestrator/__init__.py` - Graph builder, invoke_orchestrator, analyze_result
   - `src/orchestrator/nodes.py` - 8 node implementations with error handling
   - `src/orchestrator/routing.py` - Conditional routing decision functions
   - `src/orchestrator/checkpointing.py` - MemorySaver for state persistence
7. **FastAPI API Layer** (ADR-014) - HTTP endpoints with 62 tests
   - `src/api/main.py` - FastAPI app with endpoints (/health, /events, /query, etc.)
   - `src/api/models.py` - Pydantic request/response models
   - `src/api/response_builder.py` - State to API response transformation
   - `src/api/dependencies.py` - Dependency injection for orchestrator
   - `src/api/middleware.py` - Request logging with X-Request-ID tracking
8. **Service Layer** - Business logic helpers with 75 tests
   - `src/services/recurrence.py` - RRULE parsing and expansion (dateutil)
   - `src/services/queries.py` - Event/calendar queries with eager loading
   - `src/services/resources.py` - Resource availability checking
9. **Google Calendar Integration** - External calendar as primary storage with 96 tests
   - `src/integrations/base.py` - CalendarRepository protocol, CalendarEvent types
   - `src/integrations/google_calendar/` - Full Google Calendar API implementation
     - `exceptions.py` - Custom exceptions with retryable flags
     - `auth.py` - Service account authentication
     - `adapter.py` - Event ↔ Google Calendar format mapping
     - `client.py` - API client with retry logic
     - `repository.py` - Async GoogleCalendarRepository
   - `src/services/calendar_service.py` - Sync wrapper for orchestrator nodes
   - Orchestrator nodes updated to use calendar service:
     - `scheduling_node` - Finds available slots from calendar
     - `conflict_detection_node` - Queries real events for conflicts
     - `auto_confirm_node` - Persists events to calendar
     - `query_node` - Queries actual events for responses

### Not Yet Implemented
- Enhanced Agent Logic (improved prompts and structured outputs)
- Integration Tests

**Total Tests: 470 passing**

---

## Recommended Next Steps

### Phase 2: Enhanced Agent Logic (ADR-016) ✅ PARTIALLY COMPLETED
**Status: Calendar integration done, prompt improvements pending**

**Phase 2a: Calendar Integration** ✅ COMPLETED
- Scheduling Agent queries calendar for available slots
- Conflict Detection queries real events for overlaps
- Auto Confirm persists events to calendar (Google or local)
- Query Node retrieves actual events for responses

**Phase 2b: Improved Prompts** - NOT YET STARTED
- Enhance NL Parser with few-shot examples
- Add structured output parsing with Pydantic
- Improve Resolution Agent strategy generation

### Phase 3: FastAPI Endpoints (ADR-014) ✅ COMPLETED
**Status: Done - 62 tests passing**

Implemented:
- `src/api/main.py` - FastAPI app with health check and all endpoints
- `src/api/models.py` - Request/response Pydantic schemas
- `src/api/response_builder.py` - Orchestrator state → API response
- `src/api/dependencies.py` - Orchestrator dependency injection
- `src/api/middleware.py` - Request logging with X-Request-ID

Endpoints:
- `GET /health` - Health check with orchestrator status
- `POST /events` - Create event from natural language
- `GET /events` - List events with pagination
- `GET /events/{id}` - Get specific event
- `DELETE /events/{id}` - Delete event
- `POST /events/{id}/confirm` - Confirm proposed event
- `POST /events/clarify` - Submit clarification
- `POST /query` - Natural language calendar queries

### Phase 4: Service Layer ✅ COMPLETED
**Status: Done - 75 tests passing**

Implemented:
- `src/services/recurrence.py` - RRULE parsing, expansion, validation (dateutil)
- `src/services/queries.py` - Event/calendar queries with eager loading
- `src/services/resources.py` - Resource availability checking

Key functions:
- `expand_recurrence()` - Expand RRULE into instances within time window
- `get_events_in_range()` - Query events with eager-loaded relationships
- `find_overlapping_events()` - Conflict detection support
- `check_resource_availability()` - Check capacity and reservations
- `find_available_slots()` - Find open time slots for resources

### Phase 5: Integration & Testing
**Priority: Medium - ensure quality**

1. Integration tests for full workflows
2. End-to-end API tests
3. Performance testing

---

## Key Architecture Notes

- **State Flow**: All data flows through LangGraph state machine - agents don't call each other directly
- **Confidence Thresholds**: `< 0.7` → clarification, `>= 0.7` → continue
- **Two-Phase Events**: Submit → Propose → Review conflicts → Confirm
- **Model Selection**: Sonnet for reasoning, Haiku for deterministic checks
