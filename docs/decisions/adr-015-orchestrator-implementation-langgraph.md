# ADR-015: Orchestrator Implementation with LangGraph

## Status
Accepted

**Implementation Status**: Implemented
**Implementation Date**: 2026-01-12

## Context

The Family Scheduler uses a hub-and-spoke agent architecture (ADR-002) where a central Orchestrator coordinates all specialized agents. The orchestrator must manage complex workflows including:

- Sequential agent invocation (NL Parser → Scheduling → Resource Manager → Conflict Detection)
- Conditional routing based on agent outputs (low confidence → clarification, conflicts → resolution)
- State management across multi-turn conversations
- Error handling and recovery
- Audit logging of workflow execution

### Current State

**What Exists:**
- LangGraph 0.0.20 installed via LangChain
- State schema fully defined (ADR-012) with TypedDict and Pydantic models
- Agent architecture documented (ADR-002) with hub-and-spoke pattern
- API layer designed (ADR-014) expecting orchestrator invocation

**What Needs Decision:**
- LangGraph graph construction pattern
- Node implementation approach
- Routing logic implementation
- Checkpointing and state persistence
- Error handling within graph execution
- Entry and exit point design
- Testing strategy for graph workflows

### Requirements

**Functional Requirements:**
1. Route user requests through specialized agents in correct order
2. Support conditional branching based on agent outputs
3. Handle low-confidence scenarios requiring clarification
4. Manage conflict resolution workflow (proposal → user decision → confirmation)
5. Maintain conversation context for multi-turn interactions
6. Log all agent invocations for audit trail

**Non-Functional Requirements:**
1. **Deterministic**: Same input produces same routing decisions
2. **Observable**: Clear visibility into which agents executed
3. **Debuggable**: Easy to trace execution path
4. **Maintainable**: Simple to add new agents or routing rules
5. **Testable**: Unit test individual nodes, integration test full workflows

**Integration Requirements:**
1. Accepts FamilySchedulerState (ADR-012) as input
2. Returns enriched state with agent outputs
3. Invokes agents via LLM interface (ADR-011)
4. Queries database through SQLAlchemy models (ADR-013)
5. Integrates with FastAPI via dependency injection (ADR-014)

## Decision

We will implement the orchestrator using **LangGraph's StateGraph** with the following architectural decisions:

### 1. Graph Construction Pattern: StateGraph with TypedDict

**Decision:** Use `StateGraph` with `FamilySchedulerState` TypedDict as the state schema.

**Rationale:**
- StateGraph designed for complex, stateful workflows (vs MessageGraph for chat)
- TypedDict provides strong typing and IDE support
- Matches our state schema design (ADR-012)
- Natural fit for multi-agent coordination

**Implementation:**

```python
from langgraph.graph import StateGraph, END
from src.agents.state import FamilySchedulerState

def build_orchestrator_graph() -> StateGraph:
    """
    Build the LangGraph orchestrator for Family Scheduler.

    Returns compiled StateGraph ready for invocation.
    """
    # Initialize graph with state schema
    graph = StateGraph(FamilySchedulerState)

    # Add nodes (agent invocations)
    graph.add_node("nl_parser", nl_parser_node)
    graph.add_node("scheduling", scheduling_node)
    graph.add_node("resource_manager", resource_manager_node)
    graph.add_node("conflict_detection", conflict_detection_node)
    graph.add_node("resolution", resolution_node)
    graph.add_node("query", query_node)
    graph.add_node("auto_confirm", auto_confirm_node)
    graph.add_node("request_clarification", request_clarification_node)

    # Set entry point
    graph.set_entry_point("nl_parser")

    # Add edges (routing logic)
    graph.add_conditional_edges(
        "nl_parser",
        route_after_nl_parser,
        {
            "scheduling": "scheduling",
            "query": "query",
            "clarification": "request_clarification"
        }
    )

    graph.add_edge("scheduling", "resource_manager")
    graph.add_edge("resource_manager", "conflict_detection")

    graph.add_conditional_edges(
        "conflict_detection",
        route_after_conflict_detection,
        {
            "resolution": "resolution",
            "auto_confirm": "auto_confirm"
        }
    )

    graph.add_edge("resolution", END)
    graph.add_edge("auto_confirm", END)
    graph.add_edge("query", END)
    graph.add_edge("request_clarification", END)

    # Compile graph
    return graph.compile(checkpointer=get_checkpointer())
```

**Key Principles:**
- Graph is built once at startup, not per-request
- Nodes are pure functions: `(state) -> dict[str, Any]`
- Routing functions return string keys for next node
- Compilation happens once, enabling optimizations

---

### 2. Node Implementation Pattern: Pure Functions with Standardized Structure

**Decision:** Implement nodes as pure functions following a standardized template.

**Node Template:**

```python
from src.agents.state import FamilySchedulerState, AuditLogEntry
from src.agents.llm import get_llm
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def nl_parser_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    NL Parser node: Extract structured data from natural language.

    Args:
        state: Current workflow state

    Returns:
        Partial state update with agent output and audit entry
    """
    logger.info(f"Executing nl_parser_node for conversation {state['conversation_id']}")

    try:
        # 1. Extract inputs from state
        user_input = state["user_input"]
        context = state.get("context", {})

        # 2. Invoke agent logic
        llm = get_llm()
        agent_output = invoke_nl_parser_agent(llm, user_input, context)

        # 3. Create audit log entry
        audit_entry = AuditLogEntry(
            step="nl_parsing",
            timestamp=datetime.utcnow(),
            agent="nl_parser",
            confidence=agent_output["confidence"],
            explanation=agent_output["explanation"]
        )

        # 4. Return partial state update
        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "nl_parser": agent_output
            },
            "parsed_intent": agent_output["data"],
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress"
        }

    except Exception as e:
        logger.error(f"NL Parser node failed: {e}", exc_info=True)

        # Return error state
        return {
            "workflow_status": "failed",
            "errors": [
                *state.get("errors", []),
                {
                    "error_type": "agent_failure",
                    "agent": "nl_parser",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }

def invoke_nl_parser_agent(llm, user_input: str, context: dict) -> dict:
    """
    Core agent logic for NL parsing.

    Separated for testability - can unit test without graph execution.
    """
    prompt = f"""
    Extract structured event data from this natural language input:

    User Input: {user_input}
    Context: {context}

    Return JSON with: event_type, title, start_time, end_time, participants, resources, priority.
    """

    response = llm.invoke(prompt)
    parsed = parse_llm_response(response)

    return {
        "data": parsed,
        "confidence": calculate_confidence(parsed),
        "explanation": f"Understood as: {parsed.get('event_type')} event '{parsed.get('title')}'",
        "reasoning": "Clear time reference and explicit participants mentioned"
    }
```

**Node Structure:**
1. **Extract inputs** - Read required data from state
2. **Invoke agent** - Call LLM or business logic
3. **Create audit entry** - Log execution details
4. **Return partial update** - Merge new data into state
5. **Error handling** - Catch exceptions, return error state

**Benefits:**
- **Testable**: Agent logic separated from node wrapper
- **Observable**: Audit log populated automatically
- **Consistent**: All nodes follow same pattern
- **Maintainable**: Easy to understand and modify

---

### 3. Routing Logic: Conditional Edges with Decision Functions

**Decision:** Use conditional edges with decision functions that examine state.

**Routing Function Pattern:**

```python
from typing import Literal

def route_after_nl_parser(
    state: FamilySchedulerState
) -> Literal["scheduling", "query", "clarification"]:
    """
    Determine next step after NL Parser based on confidence and intent.

    Routing Rules:
    - Low confidence (<0.7) → request_clarification
    - Query intent → query agent
    - Event intent → scheduling agent
    """
    nl_output = state["agent_outputs"]["nl_parser"]
    confidence = nl_output["confidence"]
    intent = nl_output["data"].get("event_type")

    # Low confidence - need clarification
    if confidence < 0.7:
        logger.info(f"Low confidence ({confidence}), requesting clarification")
        return "clarification"

    # Query intent - route to query agent
    if intent == "query":
        logger.info("Query intent detected, routing to query agent")
        return "query"

    # Event intent - continue to scheduling
    logger.info(f"Event intent ({intent}) with high confidence, routing to scheduling")
    return "scheduling"

def route_after_conflict_detection(
    state: FamilySchedulerState
) -> Literal["resolution", "auto_confirm"]:
    """
    Determine if conflicts require resolution or auto-confirm.

    Routing Rules:
    - Conflicts detected → resolution agent
    - No conflicts → auto_confirm
    """
    conflicts = state.get("detected_conflicts", {})
    has_conflicts = conflicts.get("has_conflicts", False)

    if has_conflicts:
        conflict_count = len(conflicts.get("conflicts", []))
        logger.info(f"{conflict_count} conflicts detected, routing to resolution")
        return "resolution"

    logger.info("No conflicts detected, auto-confirming event")
    return "auto_confirm"
```

**Routing Decision Points:**

```
┌──────────────┐
│  NL Parser   │
└──────┬───────┘
       │
       ▼
   [Confidence Check]
       │
   ┌───┴────┬──────────┐
   │        │          │
confidence  query    event
  < 0.7    intent   intent
   │        │          │
   ▼        ▼          ▼
[Clarify] [Query]  [Scheduling]
   │        │          │
   └────────┴──────────┴──────▶ [END]
                       │
                       ▼
                [Resource Manager]
                       │
                       ▼
                [Conflict Detection]
                       │
                   [Has Conflicts?]
                       │
                  ┌────┴────┐
                  │         │
                  Yes       No
                  │         │
                  ▼         ▼
             [Resolution] [Auto-Confirm]
                  │         │
                  └────┬────┘
                       │
                       ▼
                     [END]
```

**Key Principles:**
- Routing functions are pure (no side effects)
- Return literal strings matching edge map keys
- Log routing decisions for observability
- Keep logic simple and testable

---

### 4. Checkpointing and State Persistence

**Decision:** Use in-memory checkpointer for Phase 1, PostgreSQL for Phase 2.

**Phase 1 Implementation:**

```python
from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer():
    """
    Get checkpointer for state persistence.

    Phase 1: In-memory (MemorySaver)
    Phase 2: PostgreSQL via LangGraph Cloud or custom
    """
    return MemorySaver()

# Usage in graph compilation
graph = graph.compile(checkpointer=get_checkpointer())

# Invocation with thread_id for persistence
final_state = graph.invoke(
    initial_state,
    config={"configurable": {"thread_id": state["conversation_id"]}}
)
```

**Benefits:**
- **Multi-turn conversations**: State persisted across requests
- **Resume workflows**: Can pause and continue later
- **Debugging**: Inspect intermediate states
- **Testing**: Deterministic execution with same thread_id

**Phase 2 Migration:**

```python
from langgraph.checkpoint.postgres import PostgresSaver

def get_checkpointer():
    """PostgreSQL-based checkpointer for production."""
    db_url = get_settings().database_url
    return PostgresSaver(db_url)
```

---

### 5. Error Handling Within Graph Execution

**Decision:** Nodes return error state instead of raising exceptions; orchestrator handles gracefully.

**Error Handling Strategy:**

```python
def scheduling_node(state: FamilySchedulerState) -> dict[str, Any]:
    """Scheduling node with error handling."""
    try:
        # Normal execution
        result = invoke_scheduling_agent(...)

        return {
            "agent_outputs": {...},
            "proposed_event": result["event"],
            "workflow_status": "in_progress"
        }

    except LLMError as e:
        # LLM API failure
        logger.error(f"LLM error in scheduling: {e}")
        return {
            "workflow_status": "failed",
            "errors": [
                *state.get("errors", []),
                {
                    "error_type": "llm_error",
                    "agent": "scheduling",
                    "message": "LLM API request failed",
                    "details": {"exception": str(e)},
                    "retryable": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }

    except DatabaseError as e:
        # Database query failure
        logger.error(f"Database error in scheduling: {e}")
        return {
            "workflow_status": "failed",
            "errors": [
                *state.get("errors", []),
                {
                    "error_type": "database_error",
                    "agent": "scheduling",
                    "message": "Failed to query available time slots",
                    "retryable": False,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }

    except Exception as e:
        # Unexpected error
        logger.exception(f"Unexpected error in scheduling: {e}")
        return {
            "workflow_status": "failed",
            "errors": [
                *state.get("errors", []),
                {
                    "error_type": "agent_failure",
                    "agent": "scheduling",
                    "message": "Unexpected error occurred",
                    "details": {"exception": str(e)},
                    "retryable": False,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
```

**Error Recovery Routing:**

```python
def route_on_error(state: FamilySchedulerState) -> Literal["continue", "end"]:
    """
    Check if workflow should continue or terminate due to errors.

    Called after each node via conditional edge.
    """
    if state["workflow_status"] == "failed":
        logger.warning("Workflow failed, terminating")
        return "end"

    return "continue"

# Add error checking to graph
graph.add_conditional_edges(
    "scheduling",
    route_on_error,
    {
        "continue": "resource_manager",
        "end": END
    }
)
```

**Key Principles:**
- Nodes never raise exceptions (graph execution continues)
- Errors stored in state for API layer to handle
- Routing functions check workflow_status
- Failed workflows terminate gracefully with error details

---

### 6. State Update Pattern: Partial Updates with Merge

**Decision:** Nodes return partial state updates that merge with existing state.

**Update Pattern:**

```python
def conflict_detection_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Conflict detection returns partial update.

    LangGraph merges returned dict with existing state.
    """
    proposed_event = state["proposed_event"]
    existing_events = query_existing_events()

    conflicts = detect_conflicts(proposed_event, existing_events)

    # Return only fields that changed
    return {
        "detected_conflicts": {
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts
        },
        "agent_outputs": {
            **state.get("agent_outputs", {}),
            "conflict_detection": {
                "data": {"conflicts": conflicts},
                "confidence": 1.0,  # Deterministic check
                "explanation": f"Found {len(conflicts)} conflicts" if conflicts else "No conflicts",
                "reasoning": "Checked time overlaps and resource availability"
            }
        },
        "audit_log": [
            *state.get("audit_log", []),
            AuditLogEntry(
                step="conflict_detection",
                timestamp=datetime.utcnow(),
                agent="conflict_detection",
                confidence=1.0,
                explanation=f"Detected {len(conflicts)} conflicts"
            )
        ]
    }
    # workflow_status, user_input, conversation_id, etc. remain unchanged
```

**Merge Behavior:**
- Top-level keys: Overwrite (e.g., `workflow_status`)
- Nested dicts: Shallow merge (e.g., `agent_outputs`)
- Lists: Replace entirely (use spread to append: `[*existing, new_item]`)

**Benefits:**
- Nodes only specify changes
- Reduces boilerplate
- Clear what each node modifies
- Type-safe with TypedDict

---

### 7. Entry and Exit Points

**Decision:** Single entry point (`nl_parser`), multiple exit points based on workflow.

**Entry Point:**

```python
graph.set_entry_point("nl_parser")

# All workflows start with natural language parsing
```

**Exit Points:**

```python
# Exit 1: Successful event creation (auto-confirmed)
graph.add_edge("auto_confirm", END)

# Exit 2: Conflicts detected (awaiting user)
graph.add_edge("resolution", END)

# Exit 3: Query answered
graph.add_edge("query", END)

# Exit 4: Low confidence (need clarification)
graph.add_edge("request_clarification", END)

# Exit 5: Error occurred
# (Handled via route_on_error conditional edge)
```

**Exit State Analysis:**

```python
def analyze_exit_state(state: FamilySchedulerState) -> str:
    """
    Determine exit reason from final state.

    Used by API response builder to format result.
    """
    if state["workflow_status"] == "failed":
        return "error"

    if state.get("detected_conflicts", {}).get("has_conflicts"):
        return "awaiting_user_resolution"

    if state["agent_outputs"].get("nl_parser", {}).get("confidence", 1.0) < 0.7:
        return "awaiting_user_clarification"

    if state["parsed_intent"].get("event_type") == "query":
        return "query_completed"

    return "event_confirmed"
```

---

### 8. Testing Strategy for Graph Workflows

**Decision:** Three-level testing approach: unit, integration, end-to-end.

**Level 1: Unit Test Individual Nodes**

```python
# tests/unit/test_orchestrator_nodes.py
from src.orchestrator.nodes import nl_parser_node
from src.agents.state import initialize_state

def test_nl_parser_node_high_confidence():
    """Test NL parser node with clear input."""
    state = initialize_state(
        user_input="Schedule soccer practice Saturday at 2pm",
        user_id="test_user"
    )

    result = nl_parser_node(state)

    assert "agent_outputs" in result
    assert "nl_parser" in result["agent_outputs"]
    assert result["agent_outputs"]["nl_parser"]["confidence"] > 0.7
    assert result["parsed_intent"]["event_type"] == "create"
    assert len(result["audit_log"]) == 1

def test_nl_parser_node_error_handling():
    """Test NL parser node handles LLM errors gracefully."""
    state = initialize_state(user_input="...", user_id="test_user")

    with mock.patch("src.orchestrator.nodes.get_llm") as mock_llm:
        mock_llm.side_effect = LLMError("API timeout")

        result = nl_parser_node(state)

        assert result["workflow_status"] == "failed"
        assert len(result["errors"]) > 0
        assert result["errors"][0]["error_type"] == "llm_error"
```

**Level 2: Integration Test Routing Logic**

```python
# tests/integration/test_orchestrator_routing.py
from src.orchestrator import build_orchestrator_graph

def test_routing_low_confidence_to_clarification():
    """Test low confidence triggers clarification request."""
    graph = build_orchestrator_graph()

    state = initialize_state(
        user_input="Schedule that thing next week",  # Ambiguous
        user_id="test_user"
    )

    final_state = graph.invoke(state)

    # Should route to clarification
    assert final_state["workflow_status"] == "awaiting_user"
    assert "request_clarification" in [entry["step"] for entry in final_state["audit_log"]]

def test_routing_no_conflicts_auto_confirm():
    """Test no conflicts routes to auto-confirm."""
    graph = build_orchestrator_graph()

    state = initialize_state(
        user_input="Schedule soccer Saturday at 2pm",
        user_id="test_user"
    )

    final_state = graph.invoke(state)

    # Should auto-confirm
    assert final_state["workflow_status"] == "completed"
    assert "auto_confirm" in [entry["step"] for entry in final_state["audit_log"]]
```

**Level 3: End-to-End Test Full Workflows**

```python
# tests/e2e/test_orchestrator_workflows.py
def test_full_event_creation_workflow():
    """Test complete event creation from NL input to confirmation."""
    graph = build_orchestrator_graph()

    state = initialize_state(
        user_input="Schedule team meeting Friday at 3pm in conference room",
        user_id="user_123"
    )

    final_state = graph.invoke(
        state,
        config={"configurable": {"thread_id": "test_thread_1"}}
    )

    # Verify workflow completed successfully
    assert final_state["workflow_status"] == "completed"

    # Verify all expected agents executed
    executed_steps = {entry["step"] for entry in final_state["audit_log"]}
    assert executed_steps == {
        "nl_parsing",
        "scheduling",
        "resource_manager",
        "conflict_detection",
        "auto_confirm"
    }

    # Verify event created
    assert final_state["proposed_event"] is not None
    assert final_state["proposed_event"]["status"] == "confirmed"

    # Verify no errors
    assert len(final_state.get("errors", [])) == 0

def test_conflict_resolution_workflow():
    """Test workflow with conflicts requiring resolution."""
    graph = build_orchestrator_graph()

    # Create first event
    state1 = initialize_state(
        user_input="Dentist appointment Saturday at 2pm",
        user_id="user_123"
    )
    graph.invoke(state1)

    # Create conflicting event
    state2 = initialize_state(
        user_input="Soccer practice Saturday at 2pm",
        user_id="user_123"
    )
    final_state = graph.invoke(state2)

    # Should detect conflict
    assert final_state["workflow_status"] == "awaiting_user"
    assert final_state["detected_conflicts"]["has_conflicts"] is True
    assert len(final_state["detected_conflicts"]["conflicts"]) > 0

    # Should propose resolutions
    assert "resolution" in final_state["agent_outputs"]
    assert len(final_state["agent_outputs"]["resolution"]["data"]["proposed_resolutions"]) > 0
```

---

## Consequences

### Positive

1. **Clear Structure**: StateGraph provides explicit workflow definition
2. **Type Safety**: TypedDict state schema catches errors at development time
3. **Observable**: Audit log tracks every agent invocation
4. **Debuggable**: Can inspect state at any point in execution
5. **Testable**: Three-level testing strategy covers all aspects
6. **Maintainable**: Consistent node pattern makes adding agents simple
7. **Flexible**: Conditional edges enable complex routing logic
8. **Persistent**: Checkpointing supports multi-turn conversations
9. **Error Resilient**: Graceful error handling prevents crashes

### Negative

1. **LangGraph Learning Curve**: Team must learn LangGraph-specific patterns
2. **State Size Growth**: Accumulating agent outputs may bloat state
3. **Checkpointer Overhead**: In-memory checkpointer won't scale to production
4. **Testing Complexity**: Full workflow tests require database setup
5. **Routing Rigidity**: Complex routing logic may become hard to follow

### Mitigations

1. **Learning Curve**: Comprehensive documentation and examples in this ADR
2. **State Size**: Implement state pruning for old audit log entries (Phase 2)
3. **Checkpointer**: Plan migration to PostgreSQL checkpointer (Phase 2)
4. **Testing Complexity**: Use pytest fixtures for database setup, factory patterns for state
5. **Routing Rigidity**: Keep routing functions simple, document decision logic

## Alternatives Considered

### Alternative 1: MessageGraph Instead of StateGraph

**Pros:**
- Simpler for chat-like interactions
- Built-in message history
- Less boilerplate

**Cons:**
- Not designed for complex stateful workflows
- Harder to integrate structured data (events, conflicts)
- Less control over state shape

**Decision:** Rejected - StateGraph better fits multi-agent orchestration

### Alternative 2: Direct Agent Invocation (No Graph)

**Pros:**
- Simpler implementation
- No LangGraph dependency
- Full control over execution

**Cons:**
- Violates hub-and-spoke architecture (ADR-002)
- Manual state management
- No checkpointing support
- Harder to visualize workflow
- More code to maintain

**Decision:** Rejected - LangGraph provides valuable orchestration features

### Alternative 3: LangChain Agents with Tools

**Pros:**
- Built-in agent patterns
- Tool calling abstractions
- Simpler for basic use cases

**Cons:**
- Less control over routing
- Agent makes routing decisions (not orchestrator)
- Harder to enforce hub-and-spoke
- Unpredictable execution paths

**Decision:** Rejected - Need deterministic orchestration

### Alternative 4: Custom State Machine

**Pros:**
- Full control
- No external dependencies
- Potentially simpler

**Cons:**
- Reinventing the wheel
- No checkpointing
- No visualization tools
- More code to maintain

**Decision:** Rejected - LangGraph provides mature solution

### Alternative 5: Workflow Engine (Temporal, Airflow)

**Pros:**
- Production-grade orchestration
- Built-in monitoring
- Distributed execution

**Cons:**
- Overkill for Phase 1
- Additional infrastructure
- Steeper learning curve
- Not LLM-focused

**Decision:** Rejected - Too heavyweight for current needs

## Implementation

### Implementation Plan

**Phase 1: Graph Structure**
1. Create `src/orchestrator/__init__.py` with `build_orchestrator_graph()`
2. Define graph with StateGraph and FamilySchedulerState
3. Add placeholder nodes (return state unchanged)
4. Add edges and routing functions
5. Compile graph with in-memory checkpointer

**Phase 2: Node Implementation**
1. Implement `nl_parser_node` with real LLM invocation
2. Implement `scheduling_node` with time slot logic
3. Implement `resource_manager_node` with capacity checking
4. Implement `conflict_detection_node` with overlap detection
5. Implement `resolution_node` with strategy generation
6. Implement `query_node` for answering questions
7. Implement `auto_confirm_node` and `request_clarification_node`

**Phase 3: Routing Logic**
1. Implement `route_after_nl_parser()` with confidence threshold
2. Implement `route_after_conflict_detection()` with conflict check
3. Add error handling routing
4. Test routing decisions with various scenarios

**Phase 4: Testing**
1. Write unit tests for each node
2. Write integration tests for routing
3. Write end-to-end workflow tests
4. Add fixtures for database setup

### Testing Strategy

**Unit Tests: Individual Nodes**
- Test node with mock state → verify partial update returned
- Test error handling → verify error state returned
- Test audit log entry creation
- Mock LLM and database calls

**Integration Tests: Routing**
- Test graph with specific inputs → verify correct path taken
- Test conditional edges trigger correctly
- Verify state flows through nodes as expected

**End-to-End Tests: Full Workflows**
- Test complete event creation workflow
- Test conflict resolution workflow
- Test low-confidence clarification workflow
- Test query workflow
- Test error recovery

### Performance Considerations

**Target Metrics:**
- Orchestrator overhead: < 100ms (excluding agent execution)
- State serialization: < 50ms per checkpoint
- Graph compilation: < 1s at startup
- Memory: < 50MB per workflow instance

**Optimization Strategies:**
- Compile graph once at startup (don't rebuild per request)
- Use in-memory checkpointer for Phase 1 (fast)
- Prune old audit log entries if state grows too large
- Profile routing function execution

### Critical Files

**New Files:**
- `src/orchestrator/__init__.py` - Graph builder, exports `build_orchestrator_graph()`
- `src/orchestrator/nodes.py` - All node implementations
- `src/orchestrator/routing.py` - Routing decision functions
- `src/orchestrator/checkpointing.py` - Checkpointer configuration

**Test Files:**
- `tests/unit/test_orchestrator_nodes.py` - Node unit tests
- `tests/integration/test_orchestrator_routing.py` - Routing tests
- `tests/e2e/test_orchestrator_workflows.py` - End-to-end workflow tests

**Modified Files:**
- `src/config.py` - Add orchestrator timeout settings
- `src/api/main.py` - Integrate orchestrator graph

### Example: Complete Node Implementation

```python
# src/orchestrator/nodes.py
from typing import Any
from src.agents.state import FamilySchedulerState, AuditLogEntry
from src.agents.llm import get_llm
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def nl_parser_node(state: FamilySchedulerState) -> dict[str, Any]:
    """
    Extract structured data from natural language input.

    Returns partial state update with:
    - agent_outputs.nl_parser: Agent output with data, confidence, explanation
    - parsed_intent: Structured event data
    - audit_log: Appended audit entry
    """
    logger.info(f"[{state['conversation_id']}] Executing NL Parser")

    try:
        user_input = state["user_input"]
        context = state.get("context", {})

        llm = get_llm()

        # Build prompt
        prompt = build_nl_parser_prompt(user_input, context)

        # Invoke LLM
        response = llm.invoke(prompt)
        parsed = parse_nl_parser_response(response)

        # Calculate confidence
        confidence = calculate_nl_confidence(parsed, user_input)

        # Build agent output
        agent_output = {
            "data": parsed,
            "confidence": confidence,
            "explanation": generate_explanation(parsed),
            "reasoning": generate_reasoning(parsed, user_input)
        }

        # Create audit entry
        audit_entry = AuditLogEntry(
            step="nl_parsing",
            timestamp=datetime.utcnow(),
            agent="nl_parser",
            confidence=confidence,
            explanation=agent_output["explanation"]
        )

        logger.info(
            f"[{state['conversation_id']}] NL Parser completed: "
            f"intent={parsed.get('event_type')}, confidence={confidence:.2f}"
        )

        return {
            "agent_outputs": {
                **state.get("agent_outputs", {}),
                "nl_parser": agent_output
            },
            "parsed_intent": parsed,
            "audit_log": [*state.get("audit_log", []), audit_entry],
            "workflow_status": "in_progress"
        }

    except Exception as e:
        logger.error(
            f"[{state['conversation_id']}] NL Parser failed: {e}",
            exc_info=True
        )

        return {
            "workflow_status": "failed",
            "errors": [
                *state.get("errors", []),
                {
                    "error_type": "agent_failure",
                    "agent": "nl_parser",
                    "message": "Failed to parse natural language input",
                    "details": {"exception": str(e)},
                    "retryable": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
```

### Example: Complete Routing Function

```python
# src/orchestrator/routing.py
from typing import Literal
from src.agents.state import FamilySchedulerState
import logging

logger = logging.getLogger(__name__)

def route_after_nl_parser(
    state: FamilySchedulerState
) -> Literal["scheduling", "query", "clarification"]:
    """
    Route after NL Parser based on confidence and intent.

    Routing Logic:
    1. If confidence < 0.7 → clarification (need more info)
    2. If intent is 'query' → query agent (answer question)
    3. Otherwise → scheduling (create/modify event)
    """
    conv_id = state["conversation_id"]
    nl_output = state["agent_outputs"]["nl_parser"]

    confidence = nl_output["confidence"]
    intent = nl_output["data"].get("event_type")

    # Check confidence threshold
    if confidence < 0.7:
        logger.info(
            f"[{conv_id}] Routing to clarification: "
            f"confidence {confidence:.2f} below threshold 0.7"
        )
        return "clarification"

    # Check intent type
    if intent == "query":
        logger.info(f"[{conv_id}] Routing to query agent: query intent detected")
        return "query"

    # Default: event creation/modification
    logger.info(
        f"[{conv_id}] Routing to scheduling: "
        f"intent={intent}, confidence={confidence:.2f}"
    )
    return "scheduling"
```

### Related ADRs

- **ADR-002**: Hub-and-Spoke Agent Architecture - Orchestrator coordinates all agents
- **ADR-012**: LangGraph State Schema - StateGraph uses FamilySchedulerState
- **ADR-013**: SQLAlchemy Database Schema - Nodes query database via ORM
- **ADR-014**: API Endpoint Design - API invokes orchestrator graph

---

**Last Updated**: 2026-01-11
**Status**: Accepted, awaiting implementation
