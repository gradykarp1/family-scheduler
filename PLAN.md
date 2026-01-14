# Implementation Plan: Family Scheduler

## Current Status

### Completed
1. **Project Architecture** - 16 ADR documents defining all system aspects
2. **Development Environment** (ADR-010, ADR-011) - Poetry, LLM providers, config management
3. **LangGraph State Schema** (ADR-012) - TypedDict state, Pydantic output models
4. **Database Models** (ADR-013) - SQLAlchemy models for family configuration
   - FamilyMember, Calendar, Resource, Constraint, UserToken, Webhook
   - Note: Events stored in Google Calendar, not locally
5. **Database Infrastructure** - Session management, GUID compatibility, soft deletion
   - Async session support (aiosqlite, asyncpg)
   - PostgreSQL checkpointing for serverless
6. **Orchestrator** (ADR-015) - LangGraph graph with 8 nodes
   - `src/orchestrator/__init__.py` - Graph builder, invoke_orchestrator, analyze_result
   - `src/orchestrator/nodes.py` - 8 node implementations with error handling
   - `src/orchestrator/routing.py` - Conditional routing decision functions
   - `src/orchestrator/checkpointing.py` - PostgreSQL/MemorySaver for state persistence
7. **FastAPI API Layer** (ADR-014) - HTTP endpoints
   - `src/api/main.py` - FastAPI app with all endpoints
   - `src/api/models.py` - Pydantic request/response models
   - `src/api/auth_routes.py` - OAuth authentication endpoints
   - `src/api/webhook_routes.py` - Webhook management endpoints
8. **Service Layer** - Business logic helpers
   - `src/services/recurrence.py` - RRULE parsing and expansion
   - `src/services/queries.py` - Event/calendar queries
   - `src/services/resources.py` - Resource availability checking
   - `src/services/calendar_service.py` - Per-user calendar access
   - `src/services/webhook_service.py` - Webhook delivery with retry
9. **Google Calendar Integration** - External calendar as primary storage
   - `src/integrations/google_calendar/` - Full Google Calendar API implementation
   - Service account AND OAuth credential support
   - Per-user calendar access via OAuth tokens
10. **Google OAuth** - Users connect their own Google Calendar
    - `src/auth/google_oauth.py` - OAuth 2.0 flow implementation
    - `src/auth/token_storage.py` - Token persistence with auto-refresh
    - `src/models/tokens.py` - UserToken model
11. **Webhook Support** - Push notifications for messaging bots
    - `src/models/webhooks.py` - Webhook registration model
    - `src/services/webhook_service.py` - HMAC-signed delivery with retry
    - Event types: event.created, event.updated, event.deleted
12. **Integration Tests** - Full workflow testing
    - `tests/integration/` - Orchestrator, API, and multi-turn conversation tests
    - pytest `integration` marker for selective running

### Infrastructure Ready
- PostgreSQL support (via `psycopg` and `langgraph-checkpoint-postgres`)
- Vercel deployment configuration (`vercel.json`)
- Production validation in config (enforces PostgreSQL in production)
- PostgreSQL checkpointing for multi-turn conversations
- Async database drivers (aiosqlite, asyncpg, greenlet)

**Total Tests: 480 passing**

---

## Implementation Phases - All Complete ✅

### Phase 1: PostgreSQL & Vercel Infrastructure ✅ COMPLETED
- PostgreSQL checkpointing with `langgraph-checkpoint-postgres`
- Production config validation (enforces PostgreSQL)
- `vercel.json` deployment configuration
- Async database session support

### Phase 2: Google OAuth for User Calendars ✅ COMPLETED
- `src/auth/google_oauth.py` - OAuth 2.0 authorization code flow
- `src/auth/token_storage.py` - Token persistence with auto-refresh
- `src/api/auth_routes.py` - /auth/google/login, /auth/google/callback, /auth/status, /auth/logout
- `src/services/calendar_service.py` - UserCalendarService for per-user access
- `src/integrations/google_calendar/auth.py` - OAuth credential support in GoogleAuthManager

### Phase 3: Complete API Endpoints ✅ COMPLETED
- `GET /events` - List events from user's Google Calendar
- `GET /events/{id}` - Get specific event details
- `DELETE /events/{id}` - Delete event from calendar
- All endpoints require OAuth authorization (401 if not connected)

### Phase 4: Webhook Support ✅ COMPLETED
- `src/models/webhooks.py` - Webhook registration model
- `src/api/webhook_routes.py` - POST/GET/DELETE /webhooks endpoints
- `src/services/webhook_service.py` - Delivery with HMAC signatures and retry logic
- Event triggers integrated into create_event and delete_event endpoints

---

## API Endpoints Summary

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/google/login` | GET | Get OAuth authorization URL |
| `/auth/google/callback` | GET | Handle OAuth callback |
| `/auth/status` | GET | Check if user has connected calendar |
| `/auth/logout` | POST | Disconnect calendar |

### Events
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/events` | POST | Create event from natural language |
| `/events` | GET | List events from user's calendar |
| `/events/{id}` | GET | Get specific event |
| `/events/{id}` | DELETE | Delete event |
| `/events/{id}/confirm` | POST | Confirm proposed event |
| `/events/clarify` | POST | Clarify low-confidence parsing |

### Webhooks
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhooks` | POST | Register new webhook |
| `/webhooks` | GET | List user's webhooks |
| `/webhooks/{id}` | GET | Get webhook details |
| `/webhooks/{id}` | DELETE | Delete webhook |
| `/webhooks/{id}/toggle` | PATCH | Enable/disable webhook |

### System
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/query` | POST | Natural language query |

---

## Key Architecture Notes

- **State Flow**: All data flows through LangGraph state machine - agents don't call each other directly
- **Confidence Thresholds**: `< 0.7` → clarification, `>= 0.7` → continue
- **Two-Phase Events**: Submit → Propose → Review conflicts → Confirm
- **Model Selection**: Sonnet for reasoning, Haiku for deterministic checks

### Data Storage Architecture

**Google Calendar (Source of Truth for Events)**
- All event data stored in Google Calendar API
- Per-user access via OAuth tokens
- Events created, updated, deleted via Google Calendar API

**PostgreSQL (Configuration & State)**
- `family_members`: Family member profiles and preferences
- `calendars`: Google Calendar references
- `resources`: Shared family resources
- `constraints`: Scheduling rules and preferences
- `user_tokens`: OAuth tokens for calendar access
- `webhooks`: Webhook registrations for notifications

---

## Potential Future Enhancements

- Performance testing and optimization
- Rate limiting for API endpoints
- Batch webhook delivery
- Webhook retry queue (Redis/PostgreSQL)
- Mobile push notifications
- Multi-family support
- Resource booking UI
