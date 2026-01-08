# Agent Architecture

## Overview

The Family Scheduler uses a hub-and-spoke agent architecture where a central Orchestrator coordinates multiple specialized agents. This pattern provides clear observability, predictable workflows, and separation of concerns.

## Architecture Pattern: Hub-and-Spoke

```
                    ┌──────────────────────────┐
                    │   Orchestrator Agent     │
                    │  (Central Coordinator)   │
                    └───────────┬──────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┬───────────┐
        │           │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼           ▼
   ┌────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌───────┐
   │   NL   │  │Schedule │ │Resource │ │Conflict │ │Resolution│ │ Query │
   │ Parser │  │  Agent  │ │ Manager │ │Detection│ │  Agent   │ │ Agent │
   └───┬────┘  └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘ └───┬───┘
       │            │            │            │            │           │
       └────────────┴────────────┴────────────┴────────────┴───────────┘
                                 │
                       Back to Orchestrator
```

**Key Principles:**
- All agent invocations go through orchestrator
- Orchestrator makes all routing decisions
- No direct agent-to-agent communication
- Each agent returns to orchestrator after completing task

**Benefits:**
- **Observability:** Single point to monitor all agent activity
- **Debuggability:** Clear execution path through orchestrator
- **Maintainability:** Predictable flow, easy to reason about
- **Extensibility:** Add new agents by updating orchestrator only

## Orchestrator Agent

**Role:** Central coordinator that manages the entire workflow

**Responsibilities:**
1. **Receive user requests** - Parse initial intent from user
2. **Route to specialized agents** - Determine which agent(s) to invoke
3. **Manage state** - Maintain conversation and workflow state
4. **Make decisions** - Determine next steps based on agent outputs
5. **Return results** - Format final response to user

**Decision Logic:**
```python
def route_next_step(state):
    if state["current_step"] == "start":
        return "nl_parser"
    elif state["current_step"] == "nl_parsing":
        if state["agent_outputs"]["nl_parser"]["confidence"] < 0.7:
            return "ask_user_clarification"
        return "scheduling"
    elif state["current_step"] == "scheduling":
        return "resource_manager"
    elif state["current_step"] == "resource_manager":
        return "conflict_detection"
    elif state["current_step"] == "conflict_detection":
        if len(state["agent_outputs"]["conflict_detection"]["data"]["conflicts"]) > 0:
            return "resolution"
        return "confirm_event"
    # ... etc
```

## Specialized Agents

### 1. NL Parser Agent

**Purpose:** Interpret natural language input and extract structured event/resource data

**Input:**
- User's natural language request
- Context from previous messages

**Output:**
```python
{
    "data": {
        "event_type": "create",  # or "modify", "cancel", "query"
        "title": str,
        "start_time": datetime (optional),
        "end_time": datetime (optional),
        "participants": [family_member_ids],
        "resources": [resource_ids],
        "recurrence_rule": str (optional),
        "priority": str (optional),
        "flexibility": str (optional)
    },
    "explanation": "I understood this as: Create a soccer practice event...",
    "confidence": 0.95,
    "reasoning": "High confidence due to explicit time and clear resource mention."
}
```

**Examples:**
- "Schedule soccer practice Saturday at 2pm" → Extract event details
- "Book the kitchen for 2 hours tomorrow evening" → Resource reservation
- "Cancel next week's dentist appointment" → Identify event to cancel

**Key Capabilities:**
- Parse relative time ("tomorrow", "next Tuesday", "this weekend")
- Identify family members by name or role ("the kids", "Mom")
- Infer missing details (default duration, priority)
- Handle ambiguity gracefully (low confidence score triggers clarification)

---

### 2. Scheduling Agent

**Purpose:** Find optimal times for events based on participant availability and constraints

**Input:**
- Event details from NL Parser
- Participant IDs
- Constraints and preferences
- Date/time hints or flexibility

**Output:**
```python
{
    "data": {
        "candidate_times": [
            {
                "start_time": "2026-01-11T14:00:00",
                "end_time": "2026-01-11T16:00:00",
                "score": 0.95,
                "available_participants": ["child_1", "parent_1"],
                "constraint_violations": []
            },
            {
                "start_time": "2026-01-11T17:00:00",
                "end_time": "2026-01-11T19:00:00",
                "score": 0.75,
                "available_participants": ["child_1"],
                "constraint_violations": ["parent_1: violates no_events_after_18:00"]
            }
        ],
        "recommended_time": "2026-01-11T14:00:00"
    },
    "explanation": "I found 2 available time slots. I recommend 2pm-4pm because all participants are available and no constraints are violated.",
    "confidence": 0.90,
    "reasoning": "High confidence - clear availability window with good constraint compliance."
}
```

**Key Capabilities:**
- Query database for participant calendars
- Evaluate soft constraints (preferences) vs hard constraints (rules)
- Score candidate times based on multiple factors
- Handle recurring event scheduling
- Consider travel time and buffer requirements

**Scoring Factors:**
- Participant availability (required vs optional)
- Constraint compliance (hard and soft)
- Preference alignment (time windows, day preferences)
- Minimal calendar fragmentation
- Minimal schedule disruption

---

### 3. Resource Manager Agent

**Purpose:** Check resource availability and manage capacity

**Input:**
- Event details
- Required resources
- Time range

**Output:**
```python
{
    "data": {
        "resource_availability": [
            {
                "resource_id": "car_1",
                "available": true,
                "current_capacity": 0,
                "max_capacity": 1,
                "conflicts": []
            },
            {
                "resource_id": "kitchen",
                "available": true,
                "current_capacity": 1,
                "max_capacity": 3,
                "conflicts": []
            }
        ],
        "all_resources_available": true
    },
    "explanation": "All requested resources are available: Family Car (0/1 capacity), Kitchen (1/3 capacity).",
    "confidence": 1.0,
    "reasoning": "Direct database query - confirmed availability."
}
```

**Key Capabilities:**
- Query ResourceReservation table for conflicts
- Calculate concurrent usage vs capacity
- Handle resources with different capacity models
- Suggest alternative resources if unavailable
- Consider resource attributes (e.g., car seats needed)

**Capacity Logic:**
```python
def check_resource_availability(resource_id, start_time, end_time):
    # Get resource capacity
    resource = db.query(Resource).get(resource_id)
    max_capacity = resource.capacity

    # Count overlapping reservations
    overlapping = db.query(ResourceReservation).filter(
        ResourceReservation.resource_id == resource_id,
        ResourceReservation.status == "confirmed",
        # Overlaps if: starts before end AND ends after start
        ResourceReservation.start_time < end_time,
        ResourceReservation.end_time > start_time
    ).count()

    return overlapping < max_capacity
```

---

### 4. Conflict Detection Agent

**Purpose:** Identify all types of conflicts for proposed events

**Input:**
- Proposed event details
- Participants
- Resources
- Existing events

**Output:**
```python
{
    "data": {
        "conflicts": [
            {
                "id": "conflict_123",
                "type": "time_conflict",
                "severity": "high",
                "conflicting_event_id": "event_456",
                "conflicting_event_title": "Dentist Appointment",
                "participants_affected": ["child_1"],
                "overlap_minutes": 60,
                "details": "2:30pm-3:30pm overlap"
            },
            {
                "id": "conflict_124",
                "type": "constraint_violation",
                "severity": "medium",
                "constraint_id": "constraint_789",
                "constraint_name": "Max 3 events per day",
                "details": "This would be the 4th event on Jan 11"
            }
        ],
        "has_conflicts": true,
        "blocking_conflicts": ["conflict_123"]
    },
    "explanation": "I found 2 conflicts: 1 high-severity time conflict with Dentist Appointment (60min overlap), and 1 medium-severity constraint violation (max events per day).",
    "confidence": 1.0,
    "reasoning": "Direct database queries - all conflicts identified."
}
```

**Conflict Types:**

1. **Time Conflicts:**
   - Participant double-booked
   - Insufficient gap between events (violates min_gap constraint)

2. **Resource Conflicts:**
   - Resource at capacity
   - Resource double-booked

3. **Constraint Violations:**
   - Hard constraints: Blocks scheduling entirely
   - Soft constraints: Suboptimal but allowed

**Detection Logic:**
```python
def detect_time_conflicts(event, participants):
    conflicts = []
    for participant in participants:
        overlapping = db.query(Event).join(EventParticipant).filter(
            EventParticipant.family_member_id == participant,
            Event.status == "confirmed",
            Event.start_time < event.end_time,
            Event.end_time > event.start_time
        ).all()

        for overlap_event in overlapping:
            conflicts.append({
                "type": "time_conflict",
                "severity": "high",
                "conflicting_event_id": overlap_event.id,
                "participants_affected": [participant]
            })
    return conflicts
```

---

### 5. Resolution Agent

**Purpose:** Suggest solutions to detected conflicts

**Input:**
- Detected conflicts from Conflict Detection Agent
- Event details
- Participant priorities and flexibility

**Output:**
```python
{
    "data": {
        "proposed_resolutions": [
            {
                "resolution_id": "res_1",
                "strategy": "move_event",
                "score": 0.90,
                "description": "Move soccer practice to 4pm-6pm",
                "changes": [
                    {
                        "event_id": "event_123",
                        "field": "start_time",
                        "old_value": "2026-01-11T14:00:00",
                        "new_value": "2026-01-11T16:00:00"
                    }
                ],
                "conflicts_resolved": ["conflict_123"],
                "side_effects": []
            },
            {
                "resolution_id": "res_2",
                "strategy": "cancel_event",
                "score": 0.50,
                "description": "Cancel dentist appointment",
                "changes": [
                    {
                        "event_id": "event_456",
                        "action": "cancel"
                    }
                ],
                "conflicts_resolved": ["conflict_123"],
                "side_effects": ["Important appointment cancelled"]
            }
        ],
        "recommended_resolution": "res_1"
    },
    "explanation": "I suggest moving soccer practice to 4pm-6pm (90% score) to avoid the dentist appointment conflict. This resolves all issues with no side effects.",
    "confidence": 0.85,
    "reasoning": "Move strategy is safer than cancellation and achieves full resolution."
}
```

**Resolution Strategies:**

1. **Move Event:** Change time/date of flexible event
2. **Shorten Event:** Reduce duration to eliminate overlap
3. **Split Event:** Break into multiple smaller events
4. **Cancel Event:** Remove low-priority event
5. **Override Constraint:** Accept soft constraint violation
6. **Alternative Resource:** Use different resource with capacity

**Scoring Factors:**
- Number of conflicts resolved
- Minimal disruption to existing events
- Respects event priorities
- Maintains user preferences
- Feasibility of implementation

---

### 6. Query Agent

**Purpose:** Answer natural language questions about schedules and availability

**Input:**
- User's natural language query
- Context

**Output:**
```python
{
    "data": {
        "query_type": "availability",
        "results": {
            "available_times": [
                {"start": "2026-01-11T10:00:00", "end": "2026-01-11T12:00:00"},
                {"start": "2026-01-11T16:00:00", "end": "2026-01-11T18:00:00"}
            ],
            "events": [
                {"id": "event_123", "title": "Dentist", "time": "2026-01-11T14:00:00"}
            ]
        }
    },
    "explanation": "Everyone is available Saturday from 10am-12pm and 4pm-6pm. The only scheduled event is the Dentist appointment at 2pm.",
    "confidence": 0.95,
    "reasoning": "Complete calendar query for all family members on requested date."
}
```

**Query Types:**
- **Availability:** "When is everyone free this weekend?"
- **Event Lookup:** "What do we have scheduled next week?"
- **Resource Status:** "Is the car available Thursday afternoon?"
- **Conflict Check:** "Can we fit in a 2-hour event on Saturday?"

---

## Agent Output Standard

All agents MUST return outputs in this format:

```python
{
    "data": {...},           # Agent-specific structured output
    "explanation": str,      # Human-readable summary
    "confidence": float,     # 0.0 to 1.0
    "reasoning": str         # Why agent made this decision
}
```

**Benefits:**
- **Structured data:** Orchestrator can programmatically process results
- **Explanation:** Users understand what happened, logs are readable
- **Confidence:** Orchestrator can request clarification if confidence is low
- **Reasoning:** Debugging and improving agent logic

---

## Workflow Example: Creating an Event

**User Input:** "Schedule soccer practice Saturday at 2pm"

**Orchestrator → NL Parser Agent:**
```
Input: "Schedule soccer practice Saturday at 2pm"
Output: {
    "data": {"event_type": "create", "title": "Soccer practice", "start_time": "2026-01-11T14:00:00", ...},
    "explanation": "Create soccer practice event...",
    "confidence": 0.95
}
State: Creates Event with status="proposed"
```

**Orchestrator → Scheduling Agent:**
```
Input: Proposed event + participants
Output: {
    "data": {"candidate_times": [...], "recommended_time": "2026-01-11T14:00:00"},
    "explanation": "Time slot is available for all participants",
    "confidence": 0.90
}
```

**Orchestrator → Resource Manager Agent:**
```
Input: Proposed event + required resources
Output: {
    "data": {"resource_availability": [...], "all_resources_available": true},
    "explanation": "All resources available",
    "confidence": 1.0
}
```

**Orchestrator → Conflict Detection Agent:**
```
Input: Proposed event + existing events
Output: {
    "data": {"conflicts": [], "has_conflicts": false},
    "explanation": "No conflicts detected",
    "confidence": 1.0
}
```

**Orchestrator Decision:**
- No conflicts detected
- Auto-confirm optimization applies
- Update Event: status="proposed" → "confirmed"
- Update ResourceReservation: status="confirmed"
- Return success to user

**User sees:** "Event confirmed! Soccer practice scheduled for Saturday Jan 11 at 2pm-4pm."

---

## Error Handling & Recovery

**Low Confidence Scenarios:**
```python
if agent_output["confidence"] < 0.7:
    # Ask user for clarification
    return "request_user_clarification"
```

**Agent Failures:**
- Orchestrator catches exceptions
- Logs error with full context
- Returns graceful error to user
- State preserved for retry

**Partial Results:**
- Agents can return partial data with explanation
- Orchestrator decides whether to proceed or request more info

---

## Testing Strategy

**Unit Tests:**
- Test each agent individually with mock inputs
- Verify output format compliance
- Test edge cases and error handling

**Integration Tests:**
- Test full workflows through orchestrator
- Verify state transitions
- Test multi-agent coordination

**Evaluation:**
- Use LangSmith for agent evaluation
- Track confidence scores vs actual correctness
- Monitor latency and token usage

---

## Future Enhancements

**Phase 2+:**
- Add learning from user corrections
- Implement agent-level caching for repeated queries
- Optimize prompts based on production data
- Add specialized agents for specific domains (travel planning, meal planning, etc.)

---

*Last Updated: 2026-01-08*
