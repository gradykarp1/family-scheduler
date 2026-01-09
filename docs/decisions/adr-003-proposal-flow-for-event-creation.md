# ADR-003: Proposal Flow for Event Creation

## Status
Accepted

## Context

When users request to create a new event, we need to decide when and how to confirm the event in the database. Several approaches are possible:

1. **Immediate Confirmation**: Create event as "confirmed" immediately upon user request
2. **Proposal-Then-Confirm**: Create event as "proposed", validate through agents, then confirm or reject
3. **Transaction with Rollback**: Create confirmed event, run validations, rollback if conflicts found
4. **Validation-First**: Run all validations before creating any database records

Key considerations:
- **Data Quality**: Ensure no invalid or conflicting events are confirmed
- **User Experience**: Provide transparency about conflicts before finalizing
- **Auditability**: Track what was proposed vs what was confirmed
- **State Management**: Clear workflow states for agent processing
- **Recovery**: Handle failures gracefully without corrupting data

The immediate confirmation approach risks creating invalid events that must be cleaned up later. The validation-first approach makes it hard to track what was proposed if validation fails.

## Decision

We will use a **proposal flow with validation pipeline** for event creation:

1. User submits natural language request
2. NL Parser creates event with `status="proposed"`
3. Event flows through validation agents (Scheduling, Resource Manager, Conflict Detection)
4. If no blocking issues: Auto-confirm (or user confirms)
5. If conflicts found: Present options to user, await decision
6. User approval → Update `status="confirmed"` and timestamp `confirmed_at`

**Status Flow:**
```
proposed → confirmed
    ↓
cancelled
```

**Database states:**
- `proposed`: Event created but not finalized, awaiting validation
- `confirmed`: Event validated and finalized, shows on calendar
- `cancelled`: Event was proposed or confirmed but cancelled

**Auto-confirmation criteria:**
- No time conflicts
- No resource conflicts
- No hard constraint violations
- Confidence scores above threshold

## Consequences

### Positive

1. **Data Quality**: Only validated events become confirmed
2. **User Control**: Users see conflicts before events are finalized
3. **Auditability**: Full history of proposals, even those that failed validation
4. **Graceful Failures**: Proposal state allows retrying validations without data loss
5. **Clear Workflow**: Explicit states make agent processing transparent
6. **Analytics**: Can track how many proposals fail and why
7. **Consistency**: Resources and events stay synchronized through status mirroring
8. **Undo-Friendly**: Can cancel proposed events before they impact schedules

### Negative

1. **Additional Complexity**: Must manage two-phase creation (propose + confirm)
2. **Database Records**: Creates records for events that may never be confirmed
3. **Query Complexity**: Queries must filter by status appropriately
4. **State Synchronization**: Must keep Event and ResourceReservation statuses in sync
5. **Cleanup Needed**: Old abandoned proposals may need garbage collection

### Mitigation Strategies

- Index the `status` field for efficient filtering
- Implement automatic cleanup of old abandoned proposals (e.g., after 24 hours)
- Use database transactions when updating Event + ResourceReservation statuses together
- Provide clear UI indicators for proposed vs confirmed events
- Log state transitions for debugging and analytics
- Make status updates atomic using database constraints

## Implementation Details

**Creating Proposed Event:**
```python
def create_proposed_event(parsed_data):
    event = Event(
        title=parsed_data["title"],
        start_time=parsed_data["start_time"],
        end_time=parsed_data["end_time"],
        status="proposed",
        proposed_at=datetime.utcnow(),
        created_by=user_id,
        ...
    )
    db.add(event)
    db.commit()
    return event
```

**Confirming Event:**
```python
def confirm_event(event_id):
    with db.begin():
        # Update event status
        event = db.query(Event).get(event_id)
        event.status = "confirmed"
        event.confirmed_at = datetime.utcnow()

        # Update associated resource reservations
        reservations = db.query(ResourceReservation).filter_by(
            event_id=event_id,
            status="proposed"
        ).all()

        for res in reservations:
            res.status = "confirmed"

        db.commit()
```

**Querying Events:**
```python
# Show only confirmed events on calendar
confirmed_events = db.query(Event).filter_by(
    status="confirmed"
).all()

# Include proposed for conflict checking
all_active = db.query(Event).filter(
    Event.status.in_(["proposed", "confirmed"])
).all()
```

## Alternatives Considered

### Immediate Confirmation
**Pros**: Simpler implementation, fewer states, immediate feedback
**Cons**: Risk of confirming invalid events, harder to handle conflicts gracefully, poor auditability
**Why not chosen**: Data quality and user experience concerns; cleanup of bad events is messy

### Validation-First (No Database Records)
**Pros**: No database pollution from failed proposals
**Cons**: Can't track what was attempted, harder to implement resolution agents (need something to reference), can't easily retry or resume workflows
**Why not chosen**: Loses auditability and makes agent workflows more complex

### Transaction with Rollback
**Pros**: Database handles cleanup automatically
**Cons**: Complex transaction management, resource reservations tricky to handle, harder to show user what was attempted
**Why not chosen**: Transaction complexity and lack of proposal history for learning/debugging

### Three-State (Draft/Proposed/Confirmed)
**Pros**: Could separate "user drafting" from "agent validating"
**Cons**: Additional complexity for marginal benefit in Phase 1
**Why not chosen**: Two states sufficient for current use cases; can add draft state later if needed

## References

- [Agent Architecture - Workflow Example](../architecture/agents.md#workflow-example-creating-an-event)
- [Data Model - Event Status Flow](../architecture/data-model.md#3-event)
- [Architecture Overview - Design Principles](../architecture/overview.md#2-proposal-flow-with-validation)

---

*Date: 2026-01-08*
*Supersedes: None*
