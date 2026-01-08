# Data Model

## Overview

The Family Scheduler data model supports:
- Multiple family members with individual calendars
- Events with flexible scheduling (one-time, recurring, proposed, confirmed)
- Shared resources with concurrent usage capacity
- Conflict detection and resolution tracking
- Flexible constraints and preferences

**Database:** PostgreSQL (also compatible with SQLite for Phase 1)

**ORM:** SQLAlchemy

## Entity Relationship Diagram

```
FamilyMember ──────┐
    │              │
    │ owns         │ participant_in
    │              │
    ▼              ▼
Calendar ────> Event ────> EventParticipant
                  │              │
                  │ has          │
                  ▼              │
          ResourceReservation ◄──┘
                  │
                  │ reserves
                  ▼
              Resource

FamilyMember ────> Constraint
                  (rules/preferences)

Conflict (references Event via JSONB)
```

---

## Core Entities

### 1. FamilyMember

Represents a person in the family who participates in events.

```python
class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, nullable=False)  # "parent", "child", "other"
    default_calendar_id = Column(UUID, ForeignKey("calendars.id"))
    preferences = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    default_calendar = relationship("Calendar", foreign_keys=[default_calendar_id])
    participations = relationship("EventParticipant", back_populates="family_member")
    constraints = relationship("Constraint", back_populates="family_member")
```

**Preferences Schema (JSONB):**
```json
{
    "time_preferences": {
        "preferred_start_time": "09:00",
        "preferred_end_time": "17:00",
        "no_events_before": "08:00",
        "no_events_after": "21:00"
    },
    "scheduling": {
        "default_event_duration_minutes": 60,
        "min_gap_between_events_minutes": 15,
        "max_events_per_day": 5
    },
    "notifications": {
        "email_enabled": true,
        "reminder_minutes_before": [60, 15]
    },
    "custom": {}
}
```

**Design Notes:**
- `preferences` is JSONB for flexibility - can add new preferences without migrations
- Base schema documented above, but allows arbitrary extensions in `custom`
- `role` helps agents understand family dynamics for scheduling

---

### 2. Calendar

Represents a calendar that contains events. Each family member has a personal calendar, plus there's a shared family calendar.

```python
class Calendar(Base):
    __tablename__ = "calendars"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "personal", "family", "shared"
    owner_id = Column(UUID, ForeignKey("family_members.id"), nullable=True)
    visibility = Column(String, nullable=False, default="family")  # "private", "family", "public"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("FamilyMember")
    events = relationship("Event", back_populates="calendar")
```

**Calendar Types:**
- **personal:** Owned by individual family member
- **family:** Shared calendar visible to all (owner_id = null)
- **shared:** Shared between subset of family members

**Visibility Levels:**
- **private:** Only owner can view
- **family:** All family members can view
- **public:** Anyone with access can view (future feature)

**Design Notes:**
- Simple visibility model for Phase 1
- Can add `CalendarPermission` table later for granular access control
- Family calendar has `owner_id = null`

---

### 3. Event

Represents a scheduled event or activity.

```python
class Event(Base):
    __tablename__ = "events"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    calendar_id = Column(UUID, ForeignKey("calendars.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    location = Column(String, nullable=True)

    # Status and workflow
    status = Column(String, nullable=False, default="proposed")  # "proposed", "confirmed", "cancelled"
    priority = Column(String, default="medium")  # "low", "medium", "high", "critical"
    flexibility = Column(String, default="fixed")  # "fixed", "preferred", "flexible"

    # Recurrence
    recurrence_rule = Column(String, nullable=True)  # iCalendar RRULE format
    recurrence_parent_id = Column(UUID, ForeignKey("events.id"), nullable=True)
    original_start_time = Column(DateTime, nullable=True)

    # Status timestamps
    proposed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Metadata
    created_by = Column(UUID, ForeignKey("family_members.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    calendar = relationship("Calendar", back_populates="events")
    creator = relationship("FamilyMember", foreign_keys=[created_by])
    participants = relationship("EventParticipant", back_populates="event")
    resource_reservations = relationship("ResourceReservation", back_populates="event")
    recurrence_parent = relationship("Event", remote_side=[id], foreign_keys=[recurrence_parent_id])

    # Indexes
    __table_args__ = (
        Index("idx_event_calendar_time", "calendar_id", "start_time", "end_time"),
        Index("idx_event_status", "status"),
        Index("idx_event_recurrence_parent", "recurrence_parent_id"),
    )
```

**Event Status Flow:**
```
proposed → confirmed
    ↓
cancelled
```

**Priority Levels:**
- **low:** Optional, easily movable
- **medium:** Normal importance
- **high:** Important, prefer not to move
- **critical:** Must not be moved (e.g., medical appointments)

**Flexibility Levels:**
- **fixed:** Cannot be moved (time is critical)
- **preferred:** This time is preferred but can move if needed
- **flexible:** Time is suggestion only, easily movable

**Recurrence Pattern (Hybrid Approach):**

**Parent Event:**
```python
{
    "id": "event_123",
    "title": "Soccer Practice",
    "start_time": "2026-01-06T14:00:00",
    "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO",
    "recurrence_parent_id": None
}
```

**Virtual Instances:**
- Generated on-the-fly when querying ("what events are on Jan 13?")
- No database records created
- Efficient storage

**Exception (Modified Instance):**
```python
{
    "id": "event_456",
    "title": "Soccer Practice",
    "recurrence_parent_id": "event_123",
    "original_start_time": "2026-01-13T14:00:00",  # Original Monday
    "start_time": "2026-01-14T14:00:00"  # Moved to Tuesday
}
```

**RRULE Examples:**
```python
# Weekly on Mondays
"RRULE:FREQ=WEEKLY;BYDAY=MO"

# Daily for 10 occurrences
"RRULE:FREQ=DAILY;COUNT=10"

# Monthly on the 15th
"RRULE:FREQ=MONTHLY;BYMONTHDAY=15"

# Every weekday (Mon-Fri)
"RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
```

**Design Notes:**
- Status timestamps enable workflow analytics
- Recurrence hybrid approach balances efficiency and flexibility
- Flexibility + priority guide conflict resolution agents

---

### 4. EventParticipant

Many-to-many relationship between Events and FamilyMembers.

```python
class EventParticipant(Base):
    __tablename__ = "event_participants"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID, ForeignKey("events.id"), nullable=False)
    family_member_id = Column(UUID, ForeignKey("family_members.id"), nullable=False)
    required = Column(Boolean, default=False)  # Is this person required?
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="participants")
    family_member = relationship("FamilyMember", back_populates="participations")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("event_id", "family_member_id", name="uq_event_participant"),
        Index("idx_participant_member", "family_member_id"),
        Index("idx_participant_event", "event_id"),
    )
```

**Required vs Optional:**
- **Required:** Event cannot proceed without this person (e.g., dentist appointment needs the patient)
- **Optional:** Nice to have but not essential (e.g., family dinner, anyone can attend)

**Design Notes:**
- Simplified for Phase 1: No invitation status (assume auto-accept)
- Can add `status` field later: "invited", "accepted", "declined", "tentative"
- `required` flag helps conflict resolution prioritize critical participants

---

### 5. Resource

Represents shared family resources that can be reserved.

```python
class Resource(Base):
    __tablename__ = "resources"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "vehicle", "room", "equipment"
    capacity = Column(Integer, nullable=False, default=1)
    attributes = Column(JSONB, default={})
    location = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reservations = relationship("ResourceReservation", back_populates="resource")
```

**Capacity Model:**
- `capacity = 1`: Exclusive use (e.g., car)
- `capacity > 1`: Concurrent use allowed (e.g., kitchen can fit 3 people)

**Example Resources:**

```python
# Family car (exclusive)
{
    "name": "Family Car",
    "type": "vehicle",
    "capacity": 1,
    "attributes": {
        "make": "Toyota",
        "model": "Camry",
        "seats": 5,
        "license_plate": "ABC123"
    }
}

# Kitchen (concurrent)
{
    "name": "Kitchen",
    "type": "room",
    "capacity": 3,
    "attributes": {
        "has_oven": true,
        "has_dishwasher": true,
        "has_microwave": true
    }
}

# Laptop (exclusive)
{
    "name": "Shared Laptop",
    "type": "equipment",
    "capacity": 1,
    "attributes": {
        "os": "macOS",
        "specs": "M2, 16GB RAM"
    }
}
```

**Design Notes:**
- `active` flag for soft deletion (don't delete if referenced by past reservations)
- `attributes` JSONB allows resource-specific metadata
- No resource-specific availability schedules (use Constraints instead if needed)

---

### 6. ResourceReservation

Tracks resource bookings, optionally linked to events.

```python
class ResourceReservation(Base):
    __tablename__ = "resource_reservations"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID, ForeignKey("resources.id"), nullable=False)
    event_id = Column(UUID, ForeignKey("events.id"), nullable=True)
    reserved_by = Column(UUID, ForeignKey("family_members.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="proposed")  # "proposed", "confirmed", "cancelled"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    resource = relationship("Resource", back_populates="reservations")
    event = relationship("Event", back_populates="resource_reservations")
    reserver = relationship("FamilyMember", foreign_keys=[reserved_by])

    # Indexes
    __table_args__ = (
        Index("idx_reservation_resource_time", "resource_id", "start_time", "end_time"),
        Index("idx_reservation_event", "event_id"),
    )
```

**Status Synchronization:**
- If linked to Event (`event_id` not null): Status mirrors Event status
- When Event: proposed → confirmed, ResourceReservation: proposed → confirmed
- When Event cancelled, ResourceReservation cancelled

**Standalone Reservations:**
```python
# Reserve car without creating event
{
    "resource_id": "car_id",
    "event_id": None,
    "reserved_by": "parent_1",
    "start_time": "2026-01-11T14:00:00",
    "end_time": "2026-01-11T16:00:00",
    "status": "confirmed",
    "notes": "Picking up groceries"
}
```

**Design Notes:**
- `event_id` optional enables standalone reservations
- Status mirroring ensures consistency with proposal flow
- Resource Manager Agent checks capacity against `confirmed` + `proposed` reservations

---

### 7. Conflict

Tracks detected scheduling conflicts and their resolutions.

```python
class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)  # "time_conflict", "resource_conflict", "constraint_violation"
    severity = Column(String, nullable=False)  # "low", "medium", "high", "critical"
    status = Column(String, nullable=False, default="detected")  # "detected", "resolved", "ignored"
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution_method = Column(String, nullable=True)  # "user_manual", "auto_confirm", "agent_suggested"
    description = Column(Text, nullable=False)
    involved_events = Column(JSONB, nullable=False)  # Array of event IDs
    involved_resources = Column(JSONB, nullable=True)  # Array of resource IDs
    proposed_resolution = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_conflict_status", "status", "detected_at"),
    )
```

**Conflict Types:**

1. **time_conflict:**
   - Participant double-booked
   - Insufficient gap between events

2. **resource_conflict:**
   - Resource at/over capacity
   - Resource double-booked

3. **constraint_violation:**
   - Hard constraint blocked
   - Soft constraint suboptimal

**Severity Levels:**
- **low:** Minor preference violation
- **medium:** Notable issue but manageable
- **high:** Significant problem requiring attention
- **critical:** Blocking issue that must be resolved

**Example Conflict:**
```python
{
    "id": "conflict_123",
    "type": "time_conflict",
    "severity": "high",
    "status": "detected",
    "detected_at": "2026-01-08T10:00:00",
    "description": "Soccer practice overlaps with dentist appointment by 60 minutes (2:30pm-3:30pm)",
    "involved_events": ["event_soccer", "event_dentist"],
    "involved_resources": null,
    "proposed_resolution": {
        "option_1": {
            "strategy": "move_event",
            "event_id": "event_soccer",
            "new_start_time": "2026-01-11T16:00:00",
            "score": 0.90
        },
        "option_2": {
            "strategy": "cancel_event",
            "event_id": "event_soccer",
            "score": 0.50
        }
    }
}
```

**Design Notes:**
- Keep conflict history for analytics and learning
- `proposed_resolution` from Resolution Agent stored for reference
- JSONB allows flexible conflict metadata

---

### 8. Constraint

Represents rules and preferences that guide scheduling.

```python
class Constraint(Base):
    __tablename__ = "constraints"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    family_member_id = Column(UUID, ForeignKey("family_members.id"), nullable=True)
    type = Column(String, nullable=False)  # "time_window", "min_gap", "max_events_per_day", "resource_priority", "custom"
    constraint_level = Column(String, nullable=False)  # "hard" (blocking) or "soft" (preference)
    priority = Column(Integer, default=5)  # 1-10, for soft constraints
    rule = Column(JSONB, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    family_member = relationship("FamilyMember", back_populates="constraints")

    # Indexes
    __table_args__ = (
        Index("idx_constraint_member", "family_member_id"),
        Index("idx_constraint_active", "active"),
    )
```

**Constraint Levels:**
- **hard:** Blocks scheduling entirely (e.g., "No events before 8am")
- **soft:** Preference that influences scoring (e.g., "Prefer morning events")

**Priority (for soft constraints):**
- 1-3: Low priority (nice to have)
- 4-7: Medium priority (preferred)
- 8-10: High priority (strong preference)

**Example Constraints:**

```python
# Hard: No early morning events
{
    "name": "No early morning events",
    "family_member_id": "child_1",
    "type": "time_window",
    "constraint_level": "hard",
    "rule": {
        "type": "no_events_before",
        "time": "08:00"
    }
}

# Soft: Prefer daytime
{
    "name": "Prefer daytime events",
    "family_member_id": "parent_1",
    "type": "time_window",
    "constraint_level": "soft",
    "priority": 7,
    "rule": {
        "type": "preferred_window",
        "start": "09:00",
        "end": "17:00"
    }
}

# Hard: Minimum gap between events
{
    "name": "Buffer time between events",
    "family_member_id": "parent_1",
    "type": "min_gap",
    "constraint_level": "hard",
    "rule": {
        "type": "min_gap_minutes",
        "minutes": 30
    }
}

# Soft: Limit daily events
{
    "name": "Limit daily events",
    "family_member_id": "child_1",
    "type": "max_events_per_day",
    "constraint_level": "soft",
    "priority": 8,
    "rule": {
        "type": "max_events_per_day",
        "count": 3
    }
}

# Family-wide constraint
{
    "name": "Family dinner time",
    "family_member_id": null,
    "type": "time_window",
    "constraint_level": "hard",
    "rule": {
        "type": "blocked_window",
        "start": "18:00",
        "end": "19:00",
        "days": ["MON", "TUE", "WED", "THU", "FRI"]
    }
}
```

**Rule Types:**
- `no_events_before` / `no_events_after`
- `preferred_window` / `blocked_window`
- `min_gap_minutes`
- `max_events_per_day` / `max_events_per_week`
- `resource_priority` (prefer certain resources)
- `custom` (extensible)

**Design Notes:**
- Family-wide constraints: `family_member_id = null`
- Flexible `rule` JSONB allows experimentation
- Agents interpret hard constraints as blocking, soft as scoring factors

---

## Queries and Operations

### Common Queries

**1. Find Events for a Date Range:**
```python
def get_events_for_range(calendar_id, start_date, end_date):
    # Get non-recurring events
    events = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.start_time >= start_date,
        Event.start_time < end_date,
        Event.status == "confirmed"
    ).all()

    # Get recurring events and expand instances
    recurring = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.recurrence_rule.isnot(None),
        Event.status == "confirmed"
    ).all()

    for parent in recurring:
        instances = expand_recurrence(parent, start_date, end_date)
        events.extend(instances)

    # Get recurrence exceptions
    exceptions = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.recurrence_parent_id.isnot(None),
        Event.start_time >= start_date,
        Event.start_time < end_date
    ).all()

    # Merge and deduplicate
    return merge_events_with_exceptions(events, exceptions)
```

**2. Check Resource Availability:**
```python
def check_resource_availability(resource_id, start_time, end_time):
    resource = db.query(Resource).get(resource_id)

    overlapping = db.query(ResourceReservation).filter(
        ResourceReservation.resource_id == resource_id,
        ResourceReservation.status.in_(["proposed", "confirmed"]),
        ResourceReservation.start_time < end_time,
        ResourceReservation.end_time > start_time
    ).count()

    return {
        "available": overlapping < resource.capacity,
        "current_usage": overlapping,
        "max_capacity": resource.capacity,
        "remaining": resource.capacity - overlapping
    }
```

**3. Find Participant Conflicts:**
```python
def find_participant_conflicts(family_member_id, start_time, end_time):
    conflicts = db.query(Event).join(EventParticipant).filter(
        EventParticipant.family_member_id == family_member_id,
        Event.status == "confirmed",
        Event.start_time < end_time,
        Event.end_time > start_time
    ).all()

    return conflicts
```

**4. Evaluate Constraints:**
```python
def check_constraints(family_member_id, event_details):
    constraints = db.query(Constraint).filter(
        or_(
            Constraint.family_member_id == family_member_id,
            Constraint.family_member_id.is_(None)  # Family-wide
        ),
        Constraint.active == True
    ).all()

    violations = []
    for constraint in constraints:
        if constraint.constraint_level == "hard":
            if violates_constraint(event_details, constraint.rule):
                violations.append({
                    "constraint_id": constraint.id,
                    "name": constraint.name,
                    "level": "hard",
                    "blocking": True
                })
        else:  # soft constraint
            if violates_constraint(event_details, constraint.rule):
                violations.append({
                    "constraint_id": constraint.id,
                    "name": constraint.name,
                    "level": "soft",
                    "priority": constraint.priority,
                    "blocking": False
                })

    return violations
```

---

## Database Migrations

Using Alembic for schema versioning:

```bash
# Create migration
alembic revision --autogenerate -m "Add resource capacity field"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Migration Strategy:**
- All schema changes via Alembic
- Test migrations on staging database first
- Keep migrations idempotent
- Include data migrations when needed

---

## Performance Considerations

**Indexes:**
- Event lookups by calendar + time range
- Participant lookups by family member
- Resource reservation lookups by resource + time
- Constraint lookups by family member + active status

**Optimization Tips:**
- Use `select_related()` / `joinedload()` to avoid N+1 queries
- Cache frequently accessed data (family members, resources)
- Partition large tables by date (future, if event volume grows)
- Use database-level constraints for data integrity

**Query Performance:**
- Typical queries: <50ms
- Complex agent workflows: 500ms-2s (including LLM calls)
- Batch operations: Use bulk insert/update

---

## Data Retention

**Retention Policy:**
- **Events:** Keep indefinitely (historical record)
- **Conflicts:** Keep for 90 days, then archive or delete
- **Audit logs:** Keep for 30 days
- **Soft-deleted resources:** Mark inactive, never hard delete

**Archival Strategy (Future):**
- Move old events to archive table
- Compress old conflicts
- Separate database for historical data

---

*Last Updated: 2026-01-08*
