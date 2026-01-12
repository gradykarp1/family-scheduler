# ADR-013: SQLAlchemy Database Schema & ORM Implementation

## Status
Accepted

**Implementation Status**: Not yet implemented
**Implementation Date**: TBD

## Context

The Family Scheduler requires a robust database layer to persist events, family members, resources, constraints, and conflicts. The database schema has been thoroughly documented in `docs/architecture/data-model.md`, but implementation decisions for the SQLAlchemy ORM layer must be made before development begins.

### Current State

**What Exists:**
- Comprehensive data model documentation with 8 core entities
- Architecture decisions for key patterns:
  - ADR-007: Hybrid Recurrence Model (RRULE-based with virtual instances)
  - ADR-008: Resource Capacity Model (integer capacity with concurrent usage)
  - ADR-009: Hard vs Soft Constraints (JSONB-stored rules with priority scoring)
- Dependencies installed: SQLAlchemy 2.0.25, Alembic 1.13.1, python-dateutil 2.8.2
- Project structure: Poetry-based with empty `src/models/` directory
- Configuration: Pydantic Settings with database_url (SQLite for Phase 1)
- Alembic initialized but no migrations yet

**What Needs Decision:**
- SQLAlchemy model organization and file structure
- Session management strategy (sync vs async)
- JSONB field handling for SQLite/PostgreSQL compatibility
- Hybrid recurrence implementation (virtual instances + exceptions)
- Query optimization patterns and indexing strategy
- Alembic migration approach
- Soft deletion implementation
- Base model design and common patterns

### Requirements

**Functional Requirements:**
1. Support all 8 entities from data-model.md: Event, EventParticipant, FamilyMember, Resource, ResourceReservation, Constraint, Conflict, Calendar
2. Implement hybrid recurrence model (ADR-007): store RRULE, generate virtual instances, handle exceptions
3. Support resource capacity checking (ADR-008): query overlapping reservations efficiently
4. Store hard/soft constraints (ADR-009): JSONB rules with priority and constraint_level
5. Handle JSONB columns for flexible data (preferences, attributes, constraint rules)
6. Support UUID primary keys across all entities
7. Maintain audit trail with created_at, updated_at timestamps
8. Enable soft deletion for historical record preservation

**Non-Functional Requirements:**
1. **Performance**: Efficiently query 1000+ events with participants and resources
2. **Scalability**: Support migration from SQLite (Phase 1) to PostgreSQL (Phase 2)
3. **Maintainability**: Clear model organization, well-documented patterns
4. **Testability**: Easy to create test fixtures, rollback transactions
5. **Compatibility**: Work with both SQLite (development) and PostgreSQL (production)

**Integration Requirements:**
1. FastAPI dependency injection for session management
2. Alembic for schema versioning and migrations
3. LangGraph agents must query database through service layer
4. Support transaction boundaries for proposal flow (ADR-003)

## Decision

We will implement SQLAlchemy 2.0 models with the following architectural decisions:

### 1. Model Organization: Modular File Structure

**Decision:** Organize models into separate files by entity domain.

```
src/models/
├── __init__.py          # Exports all models
├── base.py              # Base class, GUID type, utilities
├── family.py            # FamilyMember, Calendar
├── events.py            # Event, EventParticipant
├── resources.py         # Resource, ResourceReservation
├── constraints.py       # Constraint
└── conflicts.py         # Conflict
```

**Rationale:**
- Improves code organization and navigability
- Enables parallel development of different entity groups
- Follows domain-driven design principles
- Easier to locate and modify specific entity logic

### 2. Primary Key Strategy: UUID with TypeDecorator

**Decision:** Use UUID primary keys with a custom TypeDecorator for SQLite compatibility.

**Implementation:**
```python
from sqlalchemy import String, TypeDecorator
import uuid

class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses native UUID type for PostgreSQL, String(36) for SQLite.
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(value)

# In models:
id = Column(GUID, primary_key=True, default=uuid.uuid4)
```

**Rationale:**
- UUIDs enable distributed ID generation (agents can create IDs)
- No ID collision risk across distributed systems
- Better horizontal scaling for Phase 2
- TypeDecorator provides SQLite/PostgreSQL compatibility
- Aligns with data-model.md specification

### 3. JSONB Field Handling: Hybrid Approach

**Decision:** Use conditional JSON/JSONB column types based on database dialect.

**Implementation:**
```python
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from src.config import get_settings

def get_json_type():
    """Get database-appropriate JSON column type."""
    db_url = get_settings().database_url
    if 'postgres' in db_url:
        return JSONB
    return JSON

# In models:
preferences = Column(get_json_type(), default=dict, nullable=False)
```

**Rationale:**
- Provides PostgreSQL JSONB performance benefits when available
- Maintains SQLite compatibility for Phase 1
- Single codebase works across both databases
- Enables GIN indexes on PostgreSQL in Phase 2

**Validation Strategy:**
```python
from sqlalchemy.orm import validates

@validates('preferences')
def validate_preferences(self, key, value):
    if not isinstance(value, dict):
        raise ValueError("preferences must be dict")
    # Additional Pydantic validation here
    return value
```

### 4. Hybrid Recurrence Implementation: Service Layer Expansion

**Decision:** Store RRULE in database, expand to virtual instances in service layer.

**Architecture:**
- Event model stores `recurrence_rule` (RRULE string) and `recurrence_end_date`
- Exception events reference parent via `recurrence_parent_id` and `original_start_time`
- Service layer function expands RRULE using python-dateutil
- Virtual instances merged with exception records before returning to agents

**Service Layer Pattern:**
```python
def expand_recurring_event(
    event: Event,
    start_date: datetime,
    end_date: datetime,
    session: Session
) -> list[Event | VirtualEventInstance]:
    """Expand recurring event into instances within date range.

    1. Generate virtual instances from RRULE
    2. Query exception records
    3. Merge: replace virtual with exception where exists
    """
    # Limit expansion range
    max_range = timedelta(days=365)
    if end_date - start_date > max_range:
        raise ValueError(f"Date range exceeds maximum {max_range.days} days")

    # Generate virtual instances
    virtual = generate_virtual_instances(event, start_date, end_date)

    # Query exceptions
    exceptions = session.query(Event).filter(
        Event.recurrence_parent_id == event.id,
        Event.original_start_time.between(start_date, end_date)
    ).all()

    # Merge and return
    return merge_instances_and_exceptions(virtual, exceptions)
```

**RRULE Expansion Limits:**
- Maximum date range: 1 year (365 days)
- Supported RRULE features (Phase 1): FREQ, INTERVAL, UNTIL, COUNT, BYDAY
- Future features (Phase 2): EXDATE, RDATE, complex patterns

**Caching Strategy:**
- Phase 1: No caching (generate on-demand)
- Phase 2: Add LRU cache if performance issues arise
- Cache key: (event_id, start_date, end_date)

**Rationale:**
- Keeps database lean (no redundant instance records)
- Flexible modification of recurrence rules
- Service layer provides clean separation of concerns
- Caching can be added incrementally based on actual performance needs

### 5. Resource Capacity Query Optimization

**Decision:** Multi-column indexes on time-range queries.

**Index Strategy:**
```python
class ResourceReservation(BaseModel):
    __tablename__ = "resource_reservations"

    __table_args__ = (
        Index(
            "idx_reservation_resource_time",
            "resource_id", "start_time", "end_time"
        ),
        Index(
            "idx_reservation_status_time",
            "status", "start_time", "end_time"
        ),
    )
```

**Query Pattern:**
```python
def check_resource_availability(
    session: Session,
    resource_id: UUID,
    start_time: datetime,
    end_time: datetime
) -> bool:
    """Check if resource has capacity for time slot."""
    resource = session.query(Resource).get(resource_id)

    overlapping = session.query(ResourceReservation).filter(
        ResourceReservation.resource_id == resource_id,
        ResourceReservation.status.in_(["proposed", "confirmed"]),
        ResourceReservation.start_time < end_time,
        ResourceReservation.end_time > start_time
    ).count()

    return overlapping < resource.capacity
```

**Timezone Handling:**
- All datetime columns store UTC
- Use `DateTime(timezone=True)` in SQLAlchemy
- Convert to UTC before queries, convert to local for display

**Rationale:**
- Multi-column indexes optimize the most common query pattern
- Partial index on status filters out irrelevant records
- UTC storage eliminates timezone confusion
- Service layer helper provides clean API for agents

### 6. Session Management: Synchronous with Request Scope

**Decision:** Use synchronous SQLAlchemy with request-scoped sessions (Phase 1).

**Implementation:**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from src.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_size=5,
    pool_recycle=3600,
    pool_pre_ping=True,  # Verify connections before use
    echo=settings.is_development  # Log SQL in development
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

@contextmanager
def get_db_session() -> Session:
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# FastAPI dependency
def get_db() -> Session:
    """FastAPI dependency for request-scoped sessions."""
    with get_db_session() as session:
        yield session
```

**Session Scope Decision:**
- Per-request sessions (all agents in a request share session)
- Commit at end of request (natural transaction boundary)
- Rollback on exception (automatic cleanup)

**Connection Pool Settings:**
- Pool size: 5 connections (sufficient for Phase 1 single-user)
- Pool recycle: 3600 seconds (1 hour)
- Pool pre-ping: True (detect stale connections)

**Async Migration Plan:**
- Phase 1: Synchronous SQLAlchemy (simpler, sufficient for SQLite)
- Phase 2: Evaluate async migration when deploying to GCP
- Async provides better concurrency but adds complexity
- Most small/medium apps perform well with sync

**Rationale:**
- Synchronous is simpler for Phase 1 implementation
- Request-scoped sessions provide natural transaction boundaries
- Agents don't need concurrent database access
- Can migrate to async in Phase 2 if performance requires it

### 7. Alembic Migration Strategy

**Decision:** Use Alembic autogenerate with manual review.

**Migration Workflow:**
```bash
# After creating/modifying models
poetry run alembic revision --autogenerate -m "Add events table"

# Review auto-generated migration file
# Edit if needed (indexes, constraints, data migrations)

# Test upgrade
poetry run alembic upgrade head

# Test downgrade
poetry run alembic downgrade -1
poetry run alembic upgrade head
```

**Phase Plan:**
- **Phase 1 (SQLite)**:
  - Initial migration: Create all 8 entity tables
  - Use String(36) for UUID columns via GUID TypeDecorator
  - Use JSON for flexible columns
  - Add indexes for common query patterns

- **Phase 2 (PostgreSQL)**:
  - Migration: No schema changes needed (TypeDecorator handles it)
  - Add GIN indexes on JSONB columns for performance
  - Enable PostgreSQL-specific optimizations

**Migration Testing:**
- Wait for Phase 2 to test PostgreSQL-specific migrations
- Phase 1 focus: SQLite compatibility and correctness
- Use CI to test migrations on clean database

**Data Migrations:**
- Separate from schema migrations when possible
- Use `op.execute()` for data transformations
- Test with production data samples before deploying

**Rationale:**
- Autogenerate reduces boilerplate and errors
- Manual review catches issues autogenerate misses
- Phased approach keeps Phase 1 simple
- Testing both directions ensures migration quality

### 8. Query Optimization: Eager Loading Patterns

**Decision:** Use explicit eager loading to prevent N+1 queries.

**Standard Patterns:**
```python
from sqlalchemy.orm import joinedload, selectinload

# Pattern 1: joinedload for small result sets
events = (
    session.query(Event)
    .options(
        joinedload(Event.participants)
        .joinedload(EventParticipant.family_member)
    )
    .filter(Event.calendar_id == calendar_id)
    .all()
)

# Pattern 2: selectinload for large result sets (avoids cartesian product)
events = (
    session.query(Event)
    .options(selectinload(Event.participants))
    .filter(Event.calendar_id == calendar_id)
    .all()
)
```

**Guidelines:**
- Use `joinedload` for one-to-many with small result sets (< 100 records)
- Use `selectinload` for one-to-many with large result sets
- Always explicitly declare loading strategy in service layer
- Never rely on lazy loading in production code

**Development Tools:**
- Enable SQL echo in development: `engine = create_engine(..., echo=True)`
- Log slow queries with SQLAlchemy events
- Use pytest-sqlalchemy to detect N+1 in tests

**Rationale:**
- Explicit eager loading is predictable and performant
- Prevents surprise N+1 queries in production
- Clear performance characteristics
- Easy to optimize based on actual usage patterns

### 9. Soft Deletion Strategy

**Decision:** Use soft deletion via `deleted_at` column for all entities except EventParticipant.

**Soft Delete Scope:**
- ✅ Events - Audit trail of schedule history
- ✅ FamilyMembers - Track removed members, preserve history
- ✅ Resources - Preserve reservation history
- ✅ ResourceReservations - Historical capacity tracking
- ✅ Constraints - Understand past constraint violations
- ✅ Conflicts - Conflict resolution history
- ✅ Calendar - Preserve deleted calendars
- ❌ EventParticipants - Junction table, hard delete is fine

**Implementation:**
```python
class BaseModel(Base):
    __abstract__ = True

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        """Mark record as deleted."""
        self.deleted_at = datetime.utcnow()
```

**Query Pattern:**
```python
# Always filter soft-deleted records
active_events = session.query(Event).filter(
    Event.calendar_id == calendar_id,
    Event.deleted_at.is_(None)
).all()
```

**Index Strategy:**
- No explicit index on deleted_at
- Most queries filter by other columns first
- Compound indexes include deleted_at where beneficial

**Rationale:**
- Preserves audit trail and historical context
- Maintains referential integrity (no broken FKs)
- Enables "undo" functionality
- Essential for understanding conflict history
- FamilyMembers might be removed but history remains

### 10. Base Model Design

**Decision:** Minimal base model with common fields, extend via mixins.

**Base Model:**
```python
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime
from datetime import datetime
import uuid

Base = declarative_base()

class BaseModel(Base):
    """Base model with common fields for all entities."""
    __abstract__ = True

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def soft_delete(self):
        """Mark record as deleted."""
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self):
        """Check if record is soft-deleted."""
        return self.deleted_at is not None

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
```

**Excluded Fields:**
- `created_by` - Not needed for Phase 1 (single user)
- `version` - Optimistic locking not required initially

**Rationale:**
- Keeps base model focused on essential fields
- Timestamp tracking for all records
- Soft deletion built-in for all models
- Easy serialization with `to_dict()`
- Can add mixins later for specialized behavior

### 11. Constraint Level Storage

**Decision:** Single table with `constraint_level` column and compound indexes.

**Implementation:**
```python
class Constraint(BaseModel):
    __tablename__ = "constraints"

    family_member_id = Column(GUID, ForeignKey("family_members.id"), nullable=False)
    constraint_type = Column(String(50), nullable=False)
    constraint_level = Column(String(20), nullable=False)  # 'hard' or 'soft'
    rule = Column(get_json_type(), nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_constraint_member", "family_member_id"),
        Index("idx_constraint_level_active", "constraint_level", "active"),
    )

    @validates('constraint_level')
    def validate_level(self, key, value):
        if value not in ('hard', 'soft'):
            raise ValueError("constraint_level must be 'hard' or 'soft'")
        return value

    # Relationship
    family_member = relationship("FamilyMember", back_populates="constraints")
```

**Query Pattern:**
```python
# Get hard constraints for member
hard_constraints = session.query(Constraint).filter(
    Constraint.family_member_id == member_id,
    Constraint.constraint_level == 'hard',
    Constraint.active == True,
    Constraint.deleted_at.is_(None)
).all()
```

**Rationale:**
- Aligns with ADR-009 decision
- Compound index optimizes filtering by level and active status
- Validation ensures only valid constraint levels
- JSONB rule field provides flexibility for different constraint types

### 12. Conflict Entity Special Handling

**Decision:** Store event references as JSONB array without foreign keys.

**Implementation:**
```python
class Conflict(BaseModel):
    __tablename__ = "conflicts"

    conflict_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    involved_events = Column(get_json_type(), nullable=False)  # [uuid, uuid, ...]
    affected_participants = Column(get_json_type(), default=list)  # [uuid, uuid, ...]
    proposed_resolution = Column(get_json_type(), nullable=True)
    status = Column(String(20), default="detected", nullable=False)
    detection_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolution_date = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_conflict_detection", "detection_date"),
        Index("idx_conflict_status", "status"),
    )

    @validates('involved_events')
    def validate_events(self, key, value):
        if not isinstance(value, list):
            raise ValueError("involved_events must be list")
        # Validate all are valid UUIDs
        for event_id in value:
            try:
                uuid.UUID(str(event_id))
            except ValueError:
                raise ValueError(f"Invalid UUID: {event_id}")
        return value
```

**Rationale:**
- Conflicts may reference deleted events (historical record)
- JSONB array provides flexibility without FK constraints
- Application-level validation ensures data quality
- Can query conflicts even after events are deleted
- PostgreSQL JSONB operators enable efficient querying in Phase 2

## Consequences

### Positive

1. **Clear Organization**: Modular file structure makes codebase easy to navigate
2. **Database Agnostic**: TypeDecorator and get_json_type() enable SQLite→PostgreSQL migration
3. **Performance**: Strategic indexes and eager loading prevent common pitfalls
4. **Historical Data**: Soft deletion preserves audit trail and context
5. **Simplicity**: Synchronous SQLAlchemy keeps Phase 1 implementation straightforward
6. **Flexibility**: JSONB columns enable schema evolution without migrations
7. **Testability**: Request-scoped sessions and transaction rollback simplify testing
8. **Scalability**: UUID PKs and modular design support horizontal scaling in Phase 2

### Negative

1. **Migration Effort**: Moving to async SQLAlchemy in Phase 2 requires rewriting queries
2. **Soft Delete Complexity**: Must remember to filter `deleted_at.is_(None)` in all queries
3. **JSONB Validation**: Application-level validation required, no database constraints
4. **Recurrence Complexity**: Virtual instance generation adds service layer complexity
5. **Connection Pooling**: Sync sessions may block under high concurrency (mitigated by Phase 2 async plan)

### Mitigations

1. **Migration Effort**: Document async migration plan, use abstraction layer for queries
2. **Soft Delete**: Create query helper functions, use SQLAlchemy events or mixins
3. **JSONB Validation**: Use Pydantic models for validation, add unit tests
4. **Recurrence**: Thoroughly test expansion logic, add caching if performance issues
5. **Connection Pooling**: Monitor connection usage, increase pool size if needed

## Alternatives Considered

### Alternative 1: Async SQLAlchemy from Start

**Pros:**
- Better concurrency with async FastAPI
- No migration needed later
- Scales better under load

**Cons:**
- More complex for Phase 1 learning project
- Harder to debug and test
- Not needed for single-user SQLite usage

**Decision:** Rejected - Prioritize simplicity for Phase 1, plan migration for Phase 2

### Alternative 2: Single models.py File

**Pros:**
- All models in one place
- No circular import concerns
- Simpler initial structure

**Cons:**
- Large file becomes hard to navigate (8 entities × ~100 lines = 800+ line file)
- Merge conflicts when multiple changes
- Poor separation of concerns

**Decision:** Rejected - Modular organization provides better long-term maintainability

### Alternative 3: Hard Deletion Only

**Pros:**
- Simpler queries (no deleted_at filtering)
- Smaller database size
- No soft delete complexity

**Cons:**
- Loses audit trail
- Breaks foreign key relationships
- Can't understand historical conflicts
- No "undo" capability

**Decision:** Rejected - Audit trail essential for conflict analysis and debugging

### Alternative 4: Separate Hard/Soft Constraint Tables

**Pros:**
- No need for constraint_level column
- Slightly cleaner queries

**Cons:**
- Duplicate schema
- More complex to query both types
- Harder to rebalance constraints
- Violates ADR-009

**Decision:** Rejected - ADR-009 already decided on single table approach

### Alternative 5: Store Recurring Event Instances in Database

**Pros:**
- Simpler queries (no virtual instance generation)
- Easier to understand

**Cons:**
- Massive storage for long-running events (10 years daily = 3,650 records)
- Hard to modify recurrence rule (must update all instances)
- Violates ADR-007 decision
- Performance degradation with many instances

**Decision:** Rejected - ADR-007 hybrid model is more efficient

### Alternative 6: No Caching for Recurrence

**Pros:**
- Simpler implementation
- Always fresh data

**Cons:**
- Potentially slow for large date ranges
- Repeated expansion of same events

**Decision:** Accepted - Start without caching, add LRU cache only if performance requires

## Implementation

### Implementation Plan

**Phase 1: Foundation (Week 1)**
1. Create `src/models/base.py` with BaseModel and GUID type
2. Implement `src/models/family.py` (FamilyMember, Calendar)
3. Create session management in `src/database.py`
4. Write unit tests for base model and session management

**Phase 2: Core Entities (Week 2)**
1. Implement `src/models/events.py` (Event, EventParticipant)
2. Implement `src/models/resources.py` (Resource, ResourceReservation)
3. Generate initial Alembic migration
4. Test migration up and down

**Phase 3: Constraints & Conflicts (Week 3)**
1. Implement `src/models/constraints.py` (Constraint)
2. Implement `src/models/conflicts.py` (Conflict)
3. Create migration for new tables
4. Write unit tests for all models

**Phase 4: Service Layer (Week 4)**
1. Create query helper functions
2. Implement recurrence expansion service
3. Implement resource availability checker
4. Write integration tests for query patterns

### Testing Strategy

**Unit Tests:**
```python
# tests/unit/test_models.py
def test_event_creation(db_session):
    event = Event(
        title="Test Event",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(hours=1),
        calendar_id=uuid.uuid4()
    )
    db_session.add(event)
    db_session.commit()

    assert event.id is not None
    assert event.created_at is not None
    assert event.is_deleted is False

def test_soft_delete(db_session):
    event = Event(...)
    db_session.add(event)
    db_session.commit()

    event.soft_delete()
    db_session.commit()

    assert event.is_deleted is True
    assert event.deleted_at is not None
```

**Integration Tests:**
```python
# tests/integration/test_queries.py
def test_eager_loading_prevents_n_plus_1(db_session):
    # Create events with participants
    for i in range(10):
        event = Event(...)
        participant = EventParticipant(event=event, ...)
        db_session.add(event)
    db_session.commit()

    # Query with eager loading
    with assert_num_queries(1):  # Only one query expected
        events = (
            db_session.query(Event)
            .options(joinedload(Event.participants))
            .all()
        )
        for event in events:
            _ = event.participants  # Should not trigger query
```

**Fixtures:**
```python
# tests/conftest.py
@pytest.fixture
def db_session():
    """Provide test database session with rollback."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()
```

### Performance Benchmarks

Target metrics for Phase 1:
- Query 100 events with participants: < 50ms
- Check resource availability: < 10ms
- Expand recurring event (1 year): < 100ms
- Conflict detection scan (1000 events): < 500ms

### Critical Files

**New Files:**
- `src/models/base.py` - Base model and GUID type
- `src/models/family.py` - FamilyMember, Calendar
- `src/models/events.py` - Event, EventParticipant
- `src/models/resources.py` - Resource, ResourceReservation
- `src/models/constraints.py` - Constraint
- `src/models/conflicts.py` - Conflict
- `src/database.py` - Session management, engine creation
- `src/services/recurrence.py` - Recurring event expansion
- `src/services/queries.py` - Common query helpers

**Modified Files:**
- `src/models/__init__.py` - Export all models
- `alembic/env.py` - Import models for autogenerate

**Test Files:**
- `tests/unit/test_models.py` - Model validation tests
- `tests/integration/test_queries.py` - Query optimization tests
- `tests/integration/test_migrations.py` - Migration tests
- `tests/conftest.py` - Database fixtures

### Related ADRs

- **ADR-007**: Hybrid Recurrence Model - Defines RRULE storage and virtual instances
- **ADR-008**: Resource Capacity Model - Defines concurrent usage checking
- **ADR-009**: Hard vs Soft Constraints - Defines constraint_level storage
- **ADR-010**: Python Environment - Defines Poetry and dependency management
- **ADR-012**: LangGraph State Schema - Defines agent state (separate from DB models)

---

**Last Updated**: 2026-01-11
**Status**: Accepted, awaiting implementation
