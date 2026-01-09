# ADR-008: Resource Capacity Model

## Status
Accepted

## Context

Family scheduling involves shared resources (cars, rooms, equipment) that must be managed alongside events. We need to decide how to model resource availability and constraints.

Key scenarios to support:
- **Exclusive Resources**: Family car can only be used by one person at a time
- **Shared Resources**: Kitchen can accommodate multiple people cooking simultaneously
- **Resource Conflicts**: Detect when resources are over-booked
- **Standalone Reservations**: Reserve car for "grocery shopping" without creating calendar event

Several modeling approaches exist:

1. **Binary Availability**: Resource is either available or not (on/off)
2. **Capacity-Based**: Resource has integer capacity supporting concurrent usage
3. **Slot-Based**: Resource has fixed time slots that can be reserved
4. **Attribute-Based**: Resource attributes determine compatibility (e.g., car seats required)

Considerations:
- **Flexibility**: Model should handle both exclusive and shared resources
- **Simplicity**: Easy for agents to check availability
- **Real-World Mapping**: Natural representation of family resources
- **Conflict Detection**: Clear rules for detecting over-capacity
- **Query Performance**: Efficient availability checks

## Decision

We will use a **capacity-based model** where each resource has an integer capacity field representing how many concurrent reservations it can support.

### Model Structure

```python
class Resource(Base):
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # "vehicle", "room", "equipment"
    capacity = Column(Integer, nullable=False, default=1)
    attributes = Column(JSONB, default={})
    active = Column(Boolean, default=True)

class ResourceReservation(Base):
    id = Column(UUID, primary_key=True)
    resource_id = Column(UUID, ForeignKey("resources.id"))
    event_id = Column(UUID, ForeignKey("events.id"), nullable=True)
    reserved_by = Column(UUID, ForeignKey("family_members.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default="proposed")  # mirrors event status
```

### Capacity Semantics

- **capacity = 1**: Exclusive use (car, laptop)
- **capacity > 1**: Concurrent use allowed (kitchen with 3 capacity = up to 3 people)
- **capacity = 0**: Resource temporarily unavailable (maintenance, broken)

### Availability Check

```python
def check_resource_availability(resource_id, start_time, end_time):
    resource = db.query(Resource).get(resource_id)

    # Count overlapping reservations
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

## Consequences

### Positive

1. **Unified Model**: Single approach handles both exclusive and shared resources
2. **Simple Logic**: Availability check is straightforward integer comparison
3. **Intuitive**: Capacity naturally maps to real-world resource constraints
4. **Extensible**: Can represent various resource types with different capacities
5. **Partial Availability**: Can show "2 of 3 spots remaining" for shared resources
6. **Agent-Friendly**: Clear rules for agents to reason about resource availability
7. **Efficient Queries**: Single count query determines availability
8. **Flexible Reservations**: Supports both event-linked and standalone reservations

### Negative

1. **Limited Expressiveness**: Can't model complex constraints (e.g., "car needs 3 seats")
2. **Homogeneous Usage**: Assumes all concurrent uses are equivalent
3. **No Priority**: All reservations equal, no VIP/priority access
4. **Static Capacity**: Capacity doesn't vary by time (e.g., kitchen bigger during day)
5. **No Attributes in Availability**: Capacity check doesn't consider resource attributes

### Mitigation Strategies

**For Complex Constraints:**
- Use Constraint entities to add additional rules (e.g., "Check car has enough seats")
- Resource Manager Agent can use `attributes` field for advanced validation
- Add custom validation logic in agent prompts

**For Priority Access:**
- Can be added in Phase 2 with priority field on ResourceReservation
- For now, first-come-first-served is sufficient

**For Time-Varying Capacity:**
- Can be added later with ResourceAvailability schedule table
- Phase 1 assumes static capacity

**For Heterogeneous Usage:**
- Use attributes field to track resource-specific requirements
- Agent can validate compatibility beyond capacity

## Implementation Examples

### Exclusive Resource (Family Car)

```python
car = Resource(
    name="Family Car",
    type="vehicle",
    capacity=1,  # Only one person can use at a time
    attributes={
        "make": "Toyota",
        "model": "Camry",
        "seats": 5,
        "license_plate": "ABC123"
    }
)
```

**Reservation:**
```python
# Parent 1 reserves car 2pm-4pm
reservation1 = ResourceReservation(
    resource_id=car.id,
    reserved_by=parent1.id,
    start_time="2026-01-11T14:00:00",
    end_time="2026-01-11T16:00:00",
    status="confirmed"
)

# Parent 2 tries to reserve car 3pm-5pm (CONFLICT - overlaps)
check_availability(car.id, "2026-01-11T15:00:00", "2026-01-11T17:00:00")
# Returns: {"available": False, "current_usage": 1, "remaining": 0}
```

### Shared Resource (Kitchen)

```python
kitchen = Resource(
    name="Kitchen",
    type="room",
    capacity=3,  # Up to 3 people can use simultaneously
    attributes={
        "has_oven": True,
        "has_dishwasher": True,
        "has_microwave": True
    }
)
```

**Concurrent Reservations:**
```python
# Child 1 baking 2pm-4pm
reservation1 = ResourceReservation(
    resource_id=kitchen.id,
    reserved_by=child1.id,
    start_time="2026-01-11T14:00:00",
    end_time="2026-01-11T16:00:00",
    status="confirmed"
)

# Parent 1 cooking dinner 3pm-5pm (ALLOWED - concurrent use)
check_availability(kitchen.id, "2026-01-11T15:00:00", "2026-01-11T17:00:00")
# Returns: {"available": True, "current_usage": 1, "remaining": 2}

reservation2 = ResourceReservation(
    resource_id=kitchen.id,
    reserved_by=parent1.id,
    start_time="2026-01-11T15:00:00",
    end_time="2026-01-11T17:00:00",
    status="confirmed"
)

# Child 2 wants to make snacks 3:30pm-4pm (ALLOWED - 2 of 3 spots used)
check_availability(kitchen.id, "2026-01-11T15:30:00", "2026-01-11T16:00:00")
# Returns: {"available": True, "current_usage": 2, "remaining": 1}
```

### Standalone Reservation (No Event)

```python
# Reserve car for grocery run without creating calendar event
standalone = ResourceReservation(
    resource_id=car.id,
    event_id=None,  # Not linked to event
    reserved_by=parent1.id,
    start_time="2026-01-11T10:00:00",
    end_time="2026-01-11T11:00:00",
    status="confirmed",
    notes="Grocery shopping"
)
```

### Resource Manager Agent Integration

The Resource Manager Agent uses this capacity model to check availability:

```python
def resource_manager_agent(event_details):
    required_resources = event_details["resources"]
    start_time = event_details["start_time"]
    end_time = event_details["end_time"]

    availability = []
    all_available = True

    for resource_id in required_resources:
        result = check_resource_availability(resource_id, start_time, end_time)
        availability.append({
            "resource_id": resource_id,
            "available": result["available"],
            "current_capacity": result["current_usage"],
            "max_capacity": result["max_capacity"]
        })

        if not result["available"]:
            all_available = False

    return {
        "data": {
            "resource_availability": availability,
            "all_resources_available": all_available
        },
        "explanation": format_availability_explanation(availability),
        "confidence": 1.0
    }
```

## Alternatives Considered

### Binary Availability (Available/Unavailable)
**Pros**: Simplest possible model, easy to understand
**Cons**: Can't handle shared resources, loses information about partial availability
**Why not chosen**: Too limiting; can't represent kitchen that fits multiple people

### Slot-Based Scheduling
**Pros**: Very explicit, clear boundaries, works well for calendar-style booking
**Cons**: Inflexible, requires pre-defining slots, doesn't fit family resource model
**Why not chosen**: Over-engineered for family use case; capacity more natural

### Attribute-Based with Rules
**Pros**: Highly flexible, can model complex constraints
**Cons**: Complex to implement and reason about, agents need sophisticated logic
**Why not chosen**: Too complex for Phase 1; capacity handles 80% of use cases simply

### Separate Models for Exclusive vs Shared
**Pros**: Each optimized for use case
**Cons**: More code, duplicate logic, confusing which model to use
**Why not chosen**: Unified capacity model handles both elegantly

## Future Enhancements

**Phase 2+ Possibilities:**
- Priority levels on reservations
- Time-varying capacity schedules
- Resource groups (any car in fleet)
- Advanced attribute matching
- Resource dependencies (needs both car and car seat)

## References

- [Data Model - Resource and ResourceReservation](../architecture/data-model.md#5-resource)
- [Agent Architecture - Resource Manager Agent](../architecture/agents.md#3-resource-manager-agent)
- [ADR-003: Proposal Flow](./adr-003-proposal-flow-for-event-creation.md)

---

*Date: 2026-01-08*
*Supersedes: None*
