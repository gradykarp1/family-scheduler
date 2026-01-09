# LangGraph State Usage Examples

This document provides practical examples for working with the Family Scheduler state schema defined in ADR-012.

## Table of Contents

1. [Initializing State](#initializing-state)
2. [Agent Updates State](#agent-updates-state)
3. [Orchestrator Reads State](#orchestrator-reads-state)
4. [Handling Errors](#handling-errors)
5. [Multi-Turn Conversations](#multi-turn-conversations)
6. [State Pruning](#state-pruning)

## Initializing State

### Creating Fresh State for New Workflow

```python
from src.agents.state_utils import initialize_state

# User makes a request
state = initialize_state(
    user_input="Schedule soccer practice Saturday at 2pm",
    user_id="user_123"
)

print(f"Conversation ID: {state['conversation_id']}")
# Output: Conversation ID: conv_a3b4c5d6

print(f"Current step: {state['current_step']}")
# Output: Current step: start

print(f"Workflow status: {state['workflow_status']}")
# Output: Workflow status: in_progress
```

## Agent Updates State

### NL Parser Agent Example

```python
from datetime import datetime
from src.agents.state import AgentOutput, NLParserData
from src.agents.state_utils import update_state_with_agent_output

# NL Parser extracts structured data
parsed_data = NLParserData(
    event_type="create",
    title="Soccer practice",
    start_time="2026-01-11T14:00:00Z",
    end_time="2026-01-11T16:00:00Z",
    participants=["user_123", "user_456"],
    resources=["field_1"],
    flexibility="flexible"
)

# Create agent output following ADR-004 hybrid format
output = AgentOutput(
    data=parsed_data.model_dump(),
    explanation="Parsed as a new event creation for Saturday at 2pm with 2 participants",
    confidence=0.95,
    reasoning="Clear time reference ('Saturday at 2pm'), explicit participants mentioned",
    timestamp=datetime.utcnow().isoformat()
)

# Update state with agent output
state = update_state_with_agent_output(state, "nl_parser", output)

print(f"NL Parser confidence: {state['agent_outputs']['nl_parser']['confidence']}")
# Output: NL Parser confidence: 0.95
```

### Scheduling Agent Example

```python
from src.agents.state import TimeSlot, SchedulingData

# Scheduling Agent finds candidate times
candidates = [
    TimeSlot(
        start_time="2026-01-11T14:00:00Z",
        end_time="2026-01-11T16:00:00Z",
        score=0.95,
        available_participants=["user_123", "user_456"],
        constraint_violations=[]
    ),
    TimeSlot(
        start_time="2026-01-11T15:00:00Z",
        end_time="2026-01-11T17:00:00Z",
        score=0.82,
        available_participants=["user_123"],
        constraint_violations=["user_456_unavailable"]
    ),
]

scheduling_data = SchedulingData(
    candidate_times=candidates,
    recommended_time="2026-01-11T14:00:00Z"
)

output = AgentOutput(
    data=scheduling_data.model_dump(),
    explanation="Found 2 available time slots, recommending Saturday 2pm",
    confidence=0.88,
    reasoning="Top candidate has all participants available with no constraint violations",
    timestamp=datetime.utcnow().isoformat()
)

state = update_state_with_agent_output(state, "scheduling", output)
```

### Conflict Detection Agent Example

```python
from src.agents.state import Conflict, ConflictDetectionData

# Conflict Detection finds conflicts
conflicts = [
    Conflict(
        id="conflict_1",
        type="time_conflict",
        severity="medium",
        conflicting_event_id="event_789",
        conflicting_event_title="Dentist appointment",
        participants_affected=["user_123"],
        details="Overlaps with dentist appointment at 2:30pm"
    )
]

conflict_data = ConflictDetectionData(
    conflicts=conflicts,
    has_conflicts=True,
    blocking_conflicts=[]  # Not blocking, just soft conflict
)

output = AgentOutput(
    data=conflict_data.model_dump(),
    explanation="Found 1 medium-severity time conflict with existing appointment",
    confidence=1.0,
    reasoning="Database query confirmed overlap with existing event",
    timestamp=datetime.utcnow().isoformat()
)

state = update_state_with_agent_output(state, "conflict_detection", output)

# Store in convenience field for easy access
state["detected_conflicts"] = conflict_data.model_dump()
```

## Orchestrator Reads State

### Routing Based on Agent Confidence

```python
from src.agents.state_utils import get_agent_confidence

def route_after_nl_parsing(state):
    """Orchestrator decides next step based on NL Parser confidence."""

    confidence = get_agent_confidence(state, "nl_parser")

    if confidence is None:
        return "error"  # NL Parser didn't run

    if confidence < 0.7:
        return "request_clarification"  # Ask user for more details

    return "scheduling"  # Proceed to scheduling


# Use in routing
next_step = route_after_nl_parsing(state)
print(f"Next step: {next_step}")
# Output: Next step: scheduling (confidence was 0.95)
```

### Routing Based on Conflicts

```python
from src.agents.state_utils import has_blocking_conflicts

def route_after_conflict_detection(state):
    """Orchestrator decides if resolution is needed."""

    if has_blocking_conflicts(state):
        return "resolution"  # Must resolve conflicts

    detected = state.get("detected_conflicts", {})
    if detected.get("has_conflicts"):
        return "present_conflicts_to_user"  # Show conflicts, let user decide

    return "confirm_event"  # No conflicts, proceed


next_step = route_after_conflict_detection(state)
print(f"Next step: {next_step}")
```

### Validating State Before Transition

```python
from src.agents.state_utils import validate_state_transition

def orchestrator_transition(state, next_step):
    """Safely transition to next step with validation."""

    # Validate transition
    valid, error = validate_state_transition(state, next_step)

    if not valid:
        print(f"Cannot transition to {next_step}: {error}")
        # Handle error - maybe request clarification or retry
        return None

    # Transition is valid, proceed
    from src.agents.state_utils import transition_workflow_step
    current = state["current_step"]
    state = transition_workflow_step(state, current, next_step)

    return state


# Try to transition
state["current_step"] = "nl_parsing"
state = orchestrator_transition(state, "scheduling")

if state:
    print(f"Transitioned to: {state['current_step']}")
    # Output: Transitioned to: scheduling
```

## Handling Errors

### Adding Error to State

```python
from src.agents.state_utils import add_error, should_retry

# Agent encounters error
state = add_error(
    state,
    step="nl_parser",
    error_type="parsing_error",
    message="Could not parse time reference in input",
    retryable=True
)

print(f"Errors: {len(state['errors'])}")
# Output: Errors: 1

# Check if should retry
if should_retry(state, max_retries=3):
    print("Retrying...")
    state["retry_count"] += 1
    # Retry the agent
else:
    print("Max retries reached, failing workflow")
    state["workflow_status"] = "failed"
```

### Error Recovery Pattern

```python
def run_agent_with_retry(state, agent_name, agent_func, max_retries=3):
    """Run agent with automatic retry on failure."""

    while state["retry_count"] < max_retries:
        try:
            # Run agent
            output = agent_func(state)

            # Success - update state
            state = update_state_with_agent_output(state, agent_name, output)
            return state

        except Exception as e:
            # Add error
            state = add_error(
                state,
                step=agent_name,
                error_type=type(e).__name__,
                message=str(e),
                retryable=True
            )

            # Check if should retry
            if not should_retry(state, max_retries):
                state["workflow_status"] = "failed"
                raise

            # Increment retry count
            state["retry_count"] += 1
            print(f"Retry {state['retry_count']}/{max_retries} for {agent_name}")

    # Max retries reached
    state["workflow_status"] = "failed"
    raise Exception(f"Max retries reached for {agent_name}")
```

## Multi-Turn Conversations

### Continuing Previous Conversation

```python
# First turn - User creates event
state_turn1 = initialize_state(
    user_input="Schedule soccer practice",
    user_id="user_123"
)
# ... workflow runs ...
# State saved to checkpoint with thread_id="conv_abc123"

# Second turn - User modifies request
# LangGraph loads previous state from checkpoint
# state_turn2 = app.invoke(
#     {"user_input": "Actually make it Sunday instead"},
#     config={"configurable": {"thread_id": "conv_abc123"}}
# )

# Agent can see previous context
previous_parsed_data = state_turn2.get("parsed_event_data")
if previous_parsed_data:
    print(f"Previous title: {previous_parsed_data['title']}")
    # Agent knows this is a modification, not new event
```

### Adding Messages to Conversation

```python
# Add user message
state["messages"].append({
    "role": "user",
    "content": "Schedule soccer practice Saturday at 2pm",
    "timestamp": datetime.utcnow().isoformat()
})

# Add assistant response
state["messages"].append({
    "role": "assistant",
    "content": "I found 2 available time slots for Saturday. Would you like to proceed with 2pm?",
    "timestamp": datetime.utcnow().isoformat()
})

print(f"Messages: {len(state['messages'])}")
# Output: Messages: 2
```

## State Pruning

### Pruning Old Data to Manage State Size

```python
from src.agents.state_utils import prune_state

# State after many messages
state["messages"] = [
    {"role": "user", "content": f"Message {i}", "timestamp": "..."}
    for i in range(20)
]

# Prune to keep only recent 10 messages
state = prune_state(state, keep_messages=10)

print(f"Messages after pruning: {len(state['messages'])}")
# Output: Messages after pruning: 10
```

### Pruning After Data Extraction

```python
# After extracting to convenience field, prune original
state["parsed_event_data"] = state["agent_outputs"]["nl_parser"]["data"]

# Prune will clear the large data from agent output
state = prune_state(state)

# Metadata still available
print(f"NL Parser confidence: {state['agent_outputs']['nl_parser']['confidence']}")
# Output: NL Parser confidence: 0.95

# But large data cleared
print(f"NL Parser data: {state['agent_outputs']['nl_parser']['data']}")
# Output: NL Parser data: {}
```

## Complete Workflow Example

### End-to-End State Flow

```python
from datetime import datetime
from src.agents.state import AgentOutput, NLParserData
from src.agents.state_utils import (
    initialize_state,
    update_state_with_agent_output,
    transition_workflow_step,
    validate_state_transition,
    get_agent_confidence,
)

# 1. Initialize state
state = initialize_state(
    user_input="Schedule soccer practice Saturday at 2pm",
    user_id="user_123"
)

print(f"Step 1: Initialized - {state['current_step']}")

# 2. NL Parser runs
parsed_data = NLParserData(
    event_type="create",
    title="Soccer practice",
    start_time="2026-01-11T14:00:00Z",
    end_time="2026-01-11T16:00:00Z",
    participants=["user_123"],
    resources=["field_1"]
)

nl_output = AgentOutput(
    data=parsed_data.model_dump(),
    explanation="Parsed as new event",
    confidence=0.95,
    reasoning="Clear intent",
    timestamp=datetime.utcnow().isoformat()
)

state = update_state_with_agent_output(state, "nl_parser", nl_output)
state["parsed_event_data"] = parsed_data.model_dump()

print(f"Step 2: NL Parser complete - confidence {nl_output.confidence}")

# 3. Transition to scheduling
state = transition_workflow_step(state, "start", "nl_parsing")
state = transition_workflow_step(state, "nl_parsing", "scheduling")

print(f"Step 3: Transitioned to {state['current_step']}")

# 4. Validate before proceeding
valid, error = validate_state_transition(state, "scheduling")
if valid:
    print("Step 4: Validation passed, proceeding to scheduling")
else:
    print(f"Step 4: Validation failed - {error}")

# 5. Check workflow completion
from src.agents.state_utils import is_workflow_complete

if is_workflow_complete(state):
    print(f"Workflow complete with status: {state['workflow_status']}")
else:
    print("Workflow still in progress")

# Output:
# Step 1: Initialized - start
# Step 2: NL Parser complete - confidence 0.95
# Step 3: Transitioned to scheduling
# Step 4: Validation passed, proceeding to scheduling
# Workflow still in progress
```

## Accessor Helpers

### Quick Access to Agent Data

```python
from src.agents.state_utils import (
    get_agent_output,
    get_agent_confidence,
)

# Get full agent output
nl_output = get_agent_output(state, "nl_parser")
if nl_output:
    print(f"Explanation: {nl_output['explanation']}")
    print(f"Confidence: {nl_output['confidence']}")
    print(f"Data: {nl_output['data']}")

# Get just confidence
confidence = get_agent_confidence(state, "scheduling")
if confidence:
    print(f"Scheduling confidence: {confidence}")
else:
    print("Scheduling agent hasn't run yet")
```

## Best Practices

1. **Always use helper functions** from `state_utils.py` instead of directly manipulating state
2. **Convert Pydantic models to dicts** using `.model_dump()` before storing in TypedDict state
3. **Use ISO 8601 datetime strings** for all timestamps
4. **Validate transitions** before updating current_step
5. **Prune state** periodically to manage size
6. **Check agent confidence** before making routing decisions
7. **Add errors properly** with `add_error()` for debugging
8. **Use audit_log** to track workflow history

## Debugging Tips

### Inspecting State

```python
import json

# Pretty print state
print(json.dumps(dict(state), indent=2, default=str))

# Check audit log
for entry in state["audit_log"]:
    print(f"{entry.get('timestamp')}: {entry.get('step')} - {entry.get('action')}")

# Check which agents have run
print(f"Agents run: {list(state['agent_outputs'].keys())}")

# Check for errors
if state["errors"]:
    print("Errors occurred:")
    for error in state["errors"]:
        print(f"  - {error['step']}: {error['message']}")
```

### Testing State in Isolation

```python
# Create minimal test state
test_state = {
    "user_input": "Test",
    "user_id": "test_user",
    "conversation_id": "test_conv",
    "current_step": "nl_parsing",
    "workflow_status": "in_progress",
    "agent_outputs": {},
    "messages": [],
    "validation_results": [],
    "errors": [],
    "retry_count": 0,
    "audit_log": [],
    "created_at": datetime.utcnow().isoformat(),
    "updated_at": datetime.utcnow().isoformat()
}

# Test your code with this state
```
