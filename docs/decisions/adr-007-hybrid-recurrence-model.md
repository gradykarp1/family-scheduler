# ADR-007: Hybrid Recurrence Model

## Status
Accepted

## Context

Recurring events (weekly practices, monthly appointments, daily reminders) are a core scheduling feature. We need to decide how to model and store recurring events in the database.

Several approaches exist:

1. **Individual Records**: Create separate database record for each instance
2. **Parent with Instances**: One parent record with many child records for each occurrence
3. **Rule-Based Virtual**: Store recurrence rule, generate instances on-the-fly
4. **Hybrid**: Store rule, generate virtually, create records only for exceptions

Key considerations:
- **Storage Efficiency**: Weekly event for 1 year = 52 records vs 1 record
- **Query Performance**: Finding "events on date X" complexity
- **Exception Handling**: Modified/cancelled single instances ("move Oct 15th meeting to Oct 16th")
- **Database Size**: Recurring events could dominate database
- **Update Operations**: Changing all future instances of a recurring event
- **Delete Operations**: Deleting entire series vs single instance

Example scenarios that must be supported:
- "Soccer practice every Monday at 2pm" (recurring, no exceptions)
- "Soccer practice every Monday, but Oct 15th is moved to Tuesday Oct 16th" (modified exception)
- "Soccer practice every Monday, but Oct 15th is cancelled" (cancelled exception)
- "Change all future soccer practices from 2pm to 3pm starting Nov 1st" (series modification)

## Decision

We will use a **hybrid recurrence model**: Store the recurrence rule using iCalendar RRULE format, generate instances on-the-fly for queries, but create explicit database records only for exceptions (modifications or cancellations).

### Model Structure

**Parent Event (Recurring Series):**
```python
{
    "id": "event_123",
    "title": "Soccer Practice",
    "start_time": "2026-01-06T14:00:00",  # First occurrence
    "end_time": "2026-01-06T16:00:00",
    "recurrence_rule": "RRULE:FREQ=WEEKLY;BYDAY=MO",
    "recurrence_parent_id": None,  # This is the parent
    "status": "confirmed"
}
```

**Virtual Instances:**
- Generated on-the-fly when querying ("show me events on Jan 13, 2026")
- No database records created
- Calculated from parent's recurrence_rule

**Exception (Modified Instance):**
```python
{
    "id": "event_456",
    "title": "Soccer Practice",
    "start_time": "2026-01-14T14:00:00",  # Moved to Tuesday
    "end_time": "2026-01-14T16:00:00",
    "recurrence_parent_id": "event_123",
    "original_start_time": "2026-01-13T14:00:00",  # Original Monday
    "recurrence_rule": None,
    "status": "confirmed"
}
```

**Exception (Cancelled Instance):**
```python
{
    "id": "event_789",
    "recurrence_parent_id": "event_123",
    "original_start_time": "2026-01-20T14:00:00",
    "status": "cancelled"
}
```

### Query Logic

```python
def get_events_for_date_range(calendar_id, start_date, end_date):
    # 1. Get non-recurring events
    events = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.start_time >= start_date,
        Event.start_time < end_date,
        Event.status == "confirmed"
    ).all()

    # 2. Get recurring parents and expand
    recurring_parents = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.recurrence_rule.isnot(None),
        Event.recurrence_parent_id.is_(None),
        Event.status == "confirmed"
    ).all()

    for parent in recurring_parents:
        instances = expand_recurrence(parent, start_date, end_date)
        events.extend(instances)

    # 3. Get exceptions
    exceptions = db.query(Event).filter(
        Event.calendar_id == calendar_id,
        Event.recurrence_parent_id.isnot(None),
        Event.original_start_time >= start_date,
        Event.original_start_time < end_date
    ).all()

    # 4. Merge: Remove cancelled, replace modified
    return merge_events_with_exceptions(events, exceptions)
```

## Consequences

### Positive

1. **Storage Efficiency**: Weekly event for 1 year = 1 record (not 52)
2. **Exception Flexibility**: Can modify or cancel individual instances as needed
3. **Standard Format**: RRULE is widely used (iCalendar/RFC 5545 standard)
4. **Simple Updates**: Updating parent affects all future instances automatically
5. **Audit Trail**: Exceptions tracked explicitly in database
6. **Performance**: Most queries touch few records
7. **Scalability**: Database size grows slowly even with many recurring events
8. **Compatibility**: RRULE can be exported to other calendar systems

### Negative

1. **Query Complexity**: Must expand virtual instances and merge exceptions
2. **Computation**: Generating instances on-the-fly requires RRULE parsing
3. **Caching Needed**: Repeated queries for same date range wasteful without caching
4. **Edge Cases**: RRULE complexity can create surprising behaviors
5. **Library Dependency**: Need robust RRULE library (python-dateutil)
6. **Exception Management**: Must track original_start_time to map exceptions correctly

### Mitigation Strategies

- Use well-tested RRULE library (python-dateutil's rrule)
- Cache expanded instances for common date ranges
- Limit RRULE complexity (no EXDATE/RDATE initially)
- Comprehensive tests for exception handling
- Document RRULE format and limitations clearly
- Add database indexes on recurrence_parent_id and original_start_time
- Implement helper functions to abstract complexity from agents

## Implementation Details

### Expanding Recurrence Rule

```python
from dateutil.rrule import rrulestr
from datetime import datetime

def expand_recurrence(parent_event, start_date, end_date):
    """Generate virtual instances for a recurring event"""
    # Parse RRULE
    rrule = rrulestr(parent_event.recurrence_rule, dtstart=parent_event.start_time)

    # Calculate duration
    duration = parent_event.end_time - parent_event.start_time

    # Generate instances
    instances = []
    for occurrence_start in rrule.between(start_date, end_date, inc=True):
        instance = VirtualEvent(
            id=f"{parent_event.id}_{occurrence_start.isoformat()}",
            parent_id=parent_event.id,
            title=parent_event.title,
            start_time=occurrence_start,
            end_time=occurrence_start + duration,
            recurrence_parent_id=parent_event.id,
            status=parent_event.status
        )
        instances.append(instance)

    return instances
```

### Merging Exceptions

```python
def merge_events_with_exceptions(virtual_instances, exceptions):
    """Replace virtual instances with exceptions where they exist"""
    # Build map of original_start_time -> exception
    exception_map = {
        exc.original_start_time: exc
        for exc in exceptions
    }

    merged = []
    for instance in virtual_instances:
        if instance.start_time in exception_map:
            exception = exception_map[instance.start_time]

            # Skip cancelled exceptions
            if exception.status == "cancelled":
                continue

            # Use modified exception instead of virtual instance
            merged.append(exception)
        else:
            # Use virtual instance
            merged.append(instance)

    return merged
```

### Creating Modified Exception

```python
def modify_recurring_instance(parent_id, original_start, new_start, new_end):
    """Move a single instance of a recurring event"""
    exception = Event(
        title=parent.title,  # Copy from parent
        start_time=new_start,
        end_time=new_end,
        recurrence_parent_id=parent_id,
        original_start_time=original_start,
        recurrence_rule=None,
        status="confirmed"
    )
    db.add(exception)
    db.commit()
```

### Cancelling Single Instance

```python
def cancel_recurring_instance(parent_id, original_start):
    """Cancel a single instance of a recurring event"""
    exception = Event(
        recurrence_parent_id=parent_id,
        original_start_time=original_start,
        status="cancelled"
    )
    db.add(exception)
    db.commit()
```

## RRULE Examples

```python
# Weekly on Mondays, indefinitely
"RRULE:FREQ=WEEKLY;BYDAY=MO"

# Daily for 10 occurrences
"RRULE:FREQ=DAILY;COUNT=10"

# Every weekday (Mon-Fri)
"RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

# Monthly on the 15th
"RRULE:FREQ=MONTHLY;BYMONTHDAY=15"

# Every other week on Wednesday
"RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=WE"

# First Monday of every month
"RRULE:FREQ=MONTHLY;BYDAY=+1MO"
```

## Alternatives Considered

### Individual Records for Each Instance
**Pros**: Simple queries, explicit records, easy to understand
**Cons**: Massive database bloat (52+ records per weekly event), updating all instances requires many updates, deleting series requires many deletes
**Why not chosen**: Storage inefficiency, poor performance at scale, update operations complex

### Parent with Child Records
**Pros**: Explicit relationship, straightforward queries
**Cons**: Still creates many child records, database bloat, complex cascading updates
**Why not chosen**: Similar problems to individual records, just with foreign key relationship

### Pure Virtual (No Exceptions as Records)
**Pros**: Maximum storage efficiency, simplest data model
**Cons**: How to handle exceptions? Would need separate exception table, or complex EXDATE in RRULE
**Why not chosen**: Exception handling becomes complex, loses audit trail for modifications

### Store Expanded Instances in Separate Table
**Pros**: Pre-computed, fast queries, can index easily
**Cons**: Must regenerate when parent changes, cache invalidation complexity, storage overhead
**Why not chosen**: Adds complexity of cache management, defeats purpose of efficient storage

## References

- [RFC 5545 - iCalendar RRULE Specification](https://tools.ietf.org/html/rfc5545#section-3.3.10)
- [python-dateutil documentation](https://dateutil.readthedocs.io/en/stable/rrule.html)
- [Data Model - Event Entity](../architecture/data-model.md#3-event)

---

*Date: 2026-01-08*
*Supersedes: None*
