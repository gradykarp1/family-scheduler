# ADR-002: Hub-and-Spoke Agent Architecture

## Status
Accepted

## Context

When designing multi-agent systems, there are several architectural patterns to consider for agent communication and coordination:

1. **Peer-to-peer**: Agents communicate directly with each other
2. **Hierarchical**: Agents organized in layers with supervisor-worker relationships
3. **Hub-and-spoke**: Central orchestrator coordinates all agent interactions
4. **Event-driven**: Agents publish/subscribe to events on a message bus
5. **Blackboard**: Agents read/write to shared knowledge repository

For a learning-focused project, we need an architecture that provides:
- Clear observability of all agent interactions
- Predictable workflow execution
- Easy debugging and troubleshooting
- Simple mental model for understanding agent coordination
- Ability to inspect and control each step of the workflow

The complexity of agent-to-agent communication in peer-to-peer systems can make debugging difficult and create unpredictable execution paths.

## Decision

We will use a **hub-and-spoke architecture** where a central Orchestrator Agent coordinates all specialized agents. Key principles:

1. All agent invocations go through the Orchestrator
2. The Orchestrator makes all routing decisions
3. No direct agent-to-agent communication
4. Each specialized agent returns to the Orchestrator after completing its task
5. The Orchestrator maintains all workflow state

```
                ┌──────────────────────────┐
                │   Orchestrator Agent     │
                │  (Central Coordinator)   │
                └───────────┬──────────────┘
                            │
    ┌───────────┬───────────┼───────────┬───────────┐
    │           │           │           │           │
    ▼           ▼           ▼           ▼           ▼
┌────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐
│   NL   │  │Schedule │ │Resource │ │Conflict │ │ Query │
│ Parser │  │  Agent  │ │ Manager │ │Detection│ │ Agent │
└───┬────┘  └────┬────┘ └────┬────┘ └────┬────┘ └───┬───┘
    │            │            │            │           │
    └────────────┴────────────┴────────────┴───────────┘
                              │
                    Back to Orchestrator
```

## Consequences

### Positive

1. **Observability**: Single point to monitor all agent activity; every decision flows through one location
2. **Debuggability**: Clear execution path through orchestrator makes troubleshooting straightforward
3. **Maintainability**: Predictable flow is easy to reason about and modify
4. **Extensibility**: Adding new agents only requires updating the orchestrator's routing logic
5. **Learning-Friendly**: Simple mental model helps learners understand agent coordination
6. **State Control**: Centralized state management prevents inconsistencies
7. **Testing**: Easy to test individual agents in isolation and orchestrator logic separately
8. **Failure Recovery**: Single point to implement retry logic and error handling

### Negative

1. **Single Point of Failure**: Orchestrator failure stops all agent workflows
2. **Bottleneck Risk**: All communication passes through orchestrator (may impact performance at scale)
3. **Orchestrator Complexity**: Orchestrator contains all routing logic and can become complex
4. **Latency**: Extra hop to orchestrator adds latency vs direct agent communication
5. **Less Flexible**: Not ideal for scenarios requiring dynamic agent collaboration

### Mitigation Strategies

- Keep orchestrator routing logic simple and maintainable using clear state machine patterns
- Implement comprehensive error handling and logging in orchestrator
- Monitor orchestrator performance and optimize hot paths
- Use LangGraph's checkpoint system for failure recovery
- Consider scaling orchestrator horizontally in Phase 2 if needed
- Document routing decisions clearly in code and architecture docs

## Alternatives Considered

### Peer-to-Peer Agent Communication
**Pros**: Agents can collaborate directly, potentially more efficient, more flexible for complex collaborations
**Cons**: Difficult to debug, unpredictable execution paths, harder to maintain state consistency, complex to test
**Why not chosen**: Learning objective requires clear observability; debugging complexity defeats educational purpose

### Hierarchical with Multiple Supervisors
**Pros**: Distribute coordination responsibility, potentially better scaling
**Cons**: More complex mental model, harder to trace decisions, adds layers of indirection
**Why not chosen**: Additional complexity doesn't align with learning goals for Phase 1

### Event-Driven Architecture
**Pros**: Highly decoupled, scales well, flexible agent addition
**Cons**: Asynchronous complexity, harder to understand flow, difficult to debug across event streams
**Why not chosen**: Too complex for learning phase, makes workflow harder to follow

### Blackboard Pattern
**Pros**: Flexible knowledge sharing, agents work independently
**Cons**: Coordination logic spread across agents, harder to control workflow order
**Why not chosen**: Less predictable execution order, harder to teach and debug

## Implementation Notes

The Orchestrator Agent is implemented as a LangGraph state machine with:
- Clear routing functions for each decision point
- Structured state that includes outputs from each specialized agent
- Audit logging at each transition
- Confidence-based branching for clarification requests

Example orchestrator routing logic:
```python
def route_next_step(state):
    if state["current_step"] == "start":
        return "nl_parser"
    elif state["current_step"] == "nl_parsing":
        if state["agent_outputs"]["nl_parser"]["confidence"] < 0.7:
            return "ask_user_clarification"
        return "scheduling"
    elif state["current_step"] == "conflict_detection":
        if len(state["agent_outputs"]["conflict_detection"]["data"]["conflicts"]) > 0:
            return "resolution"
        return "confirm_event"
```

## References

- [Agent Architecture Details](../architecture/agents.md)
- [ADR-001: Agent Framework Selection](./adr-001-agent-framework-selection.md)

---

*Date: 2026-01-08*
*Supersedes: None*
