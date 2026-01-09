# ADR-004: Hybrid Agent Output Format

## Status
Accepted

## Context

Specialized agents need to return information to the orchestrator. The format of these outputs impacts:
- **Orchestrator Logic**: How the orchestrator processes results and makes routing decisions
- **User Communication**: What users see about agent actions
- **Debugging**: How developers understand what agents did and why
- **Extensibility**: How easy it is to add new agents or modify existing ones

Several output format approaches are possible:

1. **Structured Data Only**: Agents return only machine-readable data (JSON/dict)
2. **Natural Language Only**: Agents return only human-readable text
3. **Hybrid Format**: Agents return both structured data and natural language explanation
4. **Separate Channels**: Structured data returned directly, explanations logged separately

Key requirements:
- Orchestrator needs structured data for programmatic decision-making
- Users need natural language explanations to understand what happened
- Developers need context for debugging agent behavior
- Format should be consistent across all agents

## Decision

We will use a **hybrid agent output format** where every agent returns a standardized structure containing both machine-readable data and human-readable explanations.

**Standard Output Format:**
```python
{
    "data": {...},           # Agent-specific structured output
    "explanation": str,      # Human-readable summary
    "confidence": float,     # 0.0 to 1.0
    "reasoning": str         # Why agent made this decision
}
```

**Example from Scheduling Agent:**
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
            }
        ],
        "recommended_time": "2026-01-11T14:00:00"
    },
    "explanation": "I found 2 available time slots. I recommend 2pm-4pm because all participants are available and no constraints are violated.",
    "confidence": 0.90,
    "reasoning": "High confidence - clear availability window with good constraint compliance."
}
```

## Consequences

### Positive

1. **Dual Purpose**: Structured data for orchestrator logic, natural language for users
2. **Better UX**: Users understand what happened without technical jargon
3. **Debugging**: Explanations + reasoning make agent behavior transparent
4. **Confidence Tracking**: Orchestrator can request clarification for low-confidence results
5. **Observable Workflows**: Logs are human-readable without sacrificing programmatic access
6. **Consistency**: Standard format makes agent integration predictable
7. **Testability**: Can validate both data correctness and explanation quality
8. **Learning**: Reasoning field helps understand LLM decision-making process

### Negative

1. **Token Overhead**: Generating explanations costs additional LLM tokens
2. **Maintenance**: Both data and explanation must stay in sync
3. **Complexity**: Agents must produce both formats, increasing prompt complexity
4. **Prompt Length**: Requiring multiple output fields increases prompt tokens
5. **Validation**: Must validate both structured data and ensure explanation exists

### Mitigation Strategies

- Use prompt engineering to generate both outputs efficiently in a single LLM call
- Validate output format with Pydantic models to catch structure issues early
- Keep explanations concise (1-2 sentences) to minimize token usage
- Use cheaper LLM models for agents with simple explanations
- Cache agent outputs when possible to reduce redundant API calls
- Test both data and explanation quality in agent evaluations

## Implementation Details

**Pydantic Output Model:**
```python
from pydantic import BaseModel, Field

class AgentOutput(BaseModel):
    data: dict = Field(..., description="Agent-specific structured output")
    explanation: str = Field(..., description="Human-readable summary")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(..., description="Why this decision was made")

# Agent-specific data models
class SchedulingData(BaseModel):
    candidate_times: List[TimeSlot]
    recommended_time: datetime

class SchedulingAgentOutput(BaseModel):
    data: SchedulingData
    explanation: str
    confidence: float
    reasoning: str
```

**Prompt Template Example:**
```python
prompt = """
You are a scheduling agent. Analyze the event and find available time slots.

Event details: {event_details}
Participants: {participants}
Constraints: {constraints}

Return your response in this exact format:
{{
    "data": {{
        "candidate_times": [...],
        "recommended_time": "..."
    }},
    "explanation": "Brief human-readable summary of findings (1-2 sentences)",
    "confidence": 0.0-1.0,
    "reasoning": "Why you made this recommendation"
}}
"""
```

**Orchestrator Usage:**
```python
def process_scheduling(state):
    # Call scheduling agent
    result = scheduling_agent.invoke(state["event_details"])

    # Validate format
    output = SchedulingAgentOutput(**result)

    # Use structured data for logic
    if output.confidence < 0.7:
        return "request_clarification"

    # Store for next agent
    state["agent_outputs"]["scheduling"] = output.dict()

    # Log human-readable explanation
    logger.info(f"Scheduling: {output.explanation}")

    return "resource_manager"
```

## Alternatives Considered

### Structured Data Only
**Pros**: Minimal tokens, clear programmatic interface, no sync issues
**Cons**: Poor user experience, harder debugging, logs are cryptic
**Why not chosen**: User experience and debugging capabilities are critical for learning project

### Natural Language Only
**Pros**: Simple for LLM to generate, great user experience
**Cons**: Orchestrator must parse text (unreliable), hard to extract specific values, brittle logic
**Why not chosen**: Orchestrator needs reliable structured data for routing decisions

### Separate Logging Channel
**Pros**: Clean separation of concerns, data format simpler
**Cons**: Explanations divorced from data, harder to correlate, agents must make two calls
**Why not chosen**: Increases complexity and risk of explanation/data mismatch

### Tool Calling / Function Calling
**Pros**: LLMs natively support structured output via tool calls
**Cons**: Still need explanations for users, locks into specific LLM features, less portable
**Why not chosen**: Hybrid format more portable across LLM providers and includes reasoning

## References

- [Agent Architecture - Agent Output Standard](../architecture/agents.md#agent-output-standard)
- [Agent Architecture - Specialized Agents](../architecture/agents.md#specialized-agents)
- [ADR-002: Hub-and-Spoke Agent Architecture](./adr-002-hub-and-spoke-agent-architecture.md)

---

*Date: 2026-01-08*
*Supersedes: None*
