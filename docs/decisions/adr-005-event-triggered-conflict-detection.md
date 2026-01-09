# ADR-005: Event-Triggered Conflict Detection

## Status
Accepted

## Context

Conflicts can arise in scheduling when:
- Events overlap for the same participant
- Resources are double-booked or over capacity
- Constraints are violated
- Changes to existing events create new conflicts

We need to decide when and how to detect these conflicts:

1. **Synchronous Only**: Detect conflicts only during event creation/modification workflow
2. **Background Scanning**: Periodically scan entire calendar for conflicts
3. **Event-Triggered**: Detect during workflow + scan when events change
4. **Real-Time Continuous**: Monitor all changes continuously with reactive system

Key considerations:
- **Proposal Flow Integration**: Conflicts must be detected before confirming events
- **Existing Event Changes**: Modifying/cancelling events may resolve or create conflicts
- **Resource Updates**: Changing resource capacity may create conflicts
- **Constraint Changes**: Adding/modifying constraints may retroactively create conflicts
- **Performance**: Scanning all events continuously is expensive
- **Completeness**: Must catch all conflict scenarios

## Decision

We will use **synchronous validation during proposal flow + event-triggered scanning** for conflict detection.

**Two Detection Modes:**

### 1. Synchronous Validation (During Proposal Flow)
- Runs as part of event creation/modification workflow
- Conflict Detection Agent checks proposed event against existing events
- Blocks confirmation if hard conflicts found
- Reports conflicts immediately to user
- **Triggered by**: User creating/modifying event

### 2. Event-Triggered Scanning
- Background job triggered when events change status or details
- Scans for conflicts that may have been created/resolved by the change
- Creates Conflict records in database
- Notifies affected users
- **Triggered by**:
  - Event status change (proposed → confirmed, confirmed → cancelled)
  - Event time/date modification
  - Event participant changes
  - Resource capacity changes
  - Constraint additions/modifications

**No periodic full-calendar scanning in Phase 1** (can add later if needed).

## Consequences

### Positive

1. **Fast User Feedback**: Synchronous detection provides immediate conflict information during creation
2. **Comprehensive Coverage**: Event-triggered scanning catches conflicts from changes to existing events
3. **Performance**: Only scans affected events, not entire calendar
4. **Integration with Proposal Flow**: Natural fit with validation pipeline
5. **Audit Trail**: Conflict records track when conflicts were detected and resolved
6. **User Experience**: Prevents confirmation of conflicting events
7. **Efficiency**: Avoids expensive full-calendar scans

### Negative

1. **Complexity**: Two separate detection paths to implement and maintain
2. **Potential Gaps**: Rare edge cases might slip through if triggers incomplete
3. **Race Conditions**: Concurrent event modifications could theoretically create conflicts between checks
4. **Background Job Management**: Requires task queue infrastructure (Phase 2)
5. **Notification Logic**: Must determine who to notify about background-detected conflicts

### Mitigation Strategies

- Comprehensive trigger coverage: document all scenarios that should trigger scanning
- Database transactions and locking for concurrent modifications
- Fall back to synchronous validation during modification if background job fails
- Add periodic full-scan job in Phase 2 as safety net (e.g., nightly)
- Clear user notifications when background conflicts are detected
- Monitor conflict detection gaps and add triggers as needed

## Implementation Details

### Synchronous Detection (Proposal Flow)

```python
def validate_proposed_event(event_id):
    """Part of event creation workflow"""
    event = db.query(Event).get(event_id)

    # Run Conflict Detection Agent
    conflicts = conflict_detection_agent.invoke({
        "event": event,
        "participants": event.participants,
        "resources": event.resource_reservations
    })

    if conflicts["data"]["has_conflicts"]:
        # Store conflicts in database
        for conflict in conflicts["data"]["conflicts"]:
            db.add(Conflict(
                type=conflict["type"],
                severity=conflict["severity"],
                status="detected",
                involved_events=[event.id, conflict.get("conflicting_event_id")],
                description=conflict["details"]
            ))
        db.commit()

        # Block confirmation for hard conflicts
        blocking = [c for c in conflicts["data"]["conflicts"]
                    if c["severity"] in ["high", "critical"]]
        if blocking:
            return {"status": "blocked", "conflicts": conflicts}

    return {"status": "clear"}
```

### Event-Triggered Scanning

```python
@celery_app.task
def scan_for_conflicts_after_change(changed_event_id, change_type):
    """
    Background task triggered when event changes.
    Scans for new or resolved conflicts.
    """
    changed_event = db.query(Event).get(changed_event_id)

    if change_type == "cancelled":
        # Check if cancellation resolved any conflicts
        resolve_conflicts_involving_event(changed_event_id)
        return

    # Find events that might now conflict
    potentially_affected = find_potentially_affected_events(changed_event)

    for event in potentially_affected:
        # Re-run conflict detection
        conflicts = detect_conflicts_between_events(changed_event, event)

        if conflicts:
            # Create conflict records
            store_conflicts(conflicts)

            # Notify affected users
            notify_users_of_conflict(conflicts)

def find_potentially_affected_events(event):
    """Find events that might conflict with this event"""
    # Same participants in overlapping time window
    same_participant_events = db.query(Event).join(EventParticipant).filter(
        EventParticipant.family_member_id.in_([p.id for p in event.participants]),
        Event.id != event.id,
        Event.status == "confirmed",
        Event.start_time < event.end_time + timedelta(hours=2),  # Include buffer
        Event.end_time > event.start_time - timedelta(hours=2)
    ).all()

    # Same resources in overlapping time
    same_resource_events = db.query(Event).join(ResourceReservation).filter(
        ResourceReservation.resource_id.in_([r.id for r in event.resource_reservations]),
        Event.id != event.id,
        Event.status == "confirmed",
        Event.start_time < event.end_time,
        Event.end_time > event.start_time
    ).all()

    return set(same_participant_events + same_resource_events)
```

### Trigger Points

**Event Status Changes:**
```python
def confirm_event(event_id):
    event = db.query(Event).get(event_id)
    event.status = "confirmed"
    event.confirmed_at = datetime.utcnow()
    db.commit()

    # Trigger background conflict scan
    scan_for_conflicts_after_change.apply_async(
        args=[event_id, "confirmed"]
    )
```

**Event Modifications:**
```python
def update_event_time(event_id, new_start, new_end):
    event = db.query(Event).get(event_id)
    event.start_time = new_start
    event.end_time = new_end
    db.commit()

    # Trigger background conflict scan
    scan_for_conflicts_after_change.apply_async(
        args=[event_id, "time_modified"]
    )
```

## Alternatives Considered

### Synchronous Only (No Background Scanning)
**Pros**: Simpler implementation, no background job infrastructure needed
**Cons**: Misses conflicts from changes to existing events, constraint updates, resource capacity changes
**Why not chosen**: Incomplete coverage leaves gaps; users could modify confirmed events creating undetected conflicts

### Periodic Full-Calendar Scanning
**Pros**: Guaranteed to catch all conflicts eventually, simple to implement
**Cons**: Expensive to scan all events, high latency before detection, wasteful for mostly-static calendars
**Why not chosen**: Too expensive and slow; event-triggered approach more efficient

### Real-Time Continuous Monitoring
**Pros**: Immediate detection of all conflicts, most comprehensive
**Cons**: Complex infrastructure, high overhead, over-engineered for use case
**Why not chosen**: Unnecessary complexity for family scheduling scale; event-triggered sufficient

### Manual Re-Scan Only
**Pros**: Simplest possible approach, no automatic detection
**Cons**: Poor user experience, requires users to manually check, defeats purpose of intelligent system
**Why not chosen**: Doesn't leverage agent capabilities; users expect automatic conflict detection

## Phase 1 vs Phase 2

**Phase 1 (Local Development):**
- Synchronous validation only
- No background scanning (no task queue yet)
- Good enough for learning and initial testing

**Phase 2 (Cloud Deployment):**
- Add event-triggered scanning with Celery task queue
- Implement notification system
- Consider adding nightly full-scan safety net

## References

- [Agent Architecture - Conflict Detection Agent](../architecture/agents.md#4-conflict-detection-agent)
- [Data Model - Conflict Entity](../architecture/data-model.md#7-conflict)
- [ADR-003: Proposal Flow for Event Creation](./adr-003-proposal-flow-for-event-creation.md)
- [Infrastructure - Agent Scaling Workflow](../architecture/infrastructure.md#agent-scaling-workflow)

---

*Date: 2026-01-08*
*Supersedes: None*
