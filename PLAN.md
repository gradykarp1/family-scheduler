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

### Not Yet Implemented
- Enhanced Agent Logic (more sophisticated prompts and database integration)
- Service Layer (recurrence expansion, query helpers)
- Integration Tests

**Total Tests: 300 passing**

---

## Recommended Next Steps

### Phase 2: Enhanced Agent Logic (ADR-016)
**Priority: High - improve agent quality**

The orchestrator nodes have basic implementations. Enhance them with:

**Phase 2a: Database Integration**
- Connect Scheduling Agent to query existing events
- Connect Resource Manager to check actual availability
- Connect Conflict Detection to find real overlaps

**Phase 2b: Improved Prompts**
- Enhance NL Parser with few-shot examples
- Add structured output parsing with Pydantic
- Improve Resolution Agent strategy generation

Each agent enhancement needs:
- Database session integration
- Pydantic output schemas with validation
- Improved prompt templates
- Higher test coverage

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

### Phase 4: Service Layer
**Priority: Medium - helper functions for agents**

1. Create `src/services/recurrence.py` - RRULE expansion
2. Create `src/services/queries.py` - Common query patterns with eager loading
3. Create `src/services/resources.py` - Resource availability checking

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
