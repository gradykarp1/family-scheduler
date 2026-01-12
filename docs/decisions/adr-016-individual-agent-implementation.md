# ADR-016: Individual Agent Implementation & Prompt Engineering

## Status
Accepted

**Implementation Status**: Not yet implemented
**Implementation Date**: TBD

## Context

The Family Scheduler orchestrator (ADR-015) coordinates 6 specialized agents, each responsible for a specific aspect of event scheduling. Each agent must:

- Process inputs from the orchestrator state
- Invoke LLM with carefully designed prompts
- Parse structured outputs reliably
- Calculate confidence scores
- Handle errors gracefully
- Return standardized output format (data, confidence, explanation, reasoning) per ADR-004

### Current State

**What Exists:**
- LLM interface implemented (ADR-011) with Claude Sonnet 4 and Haiku
- Agent output format defined (ADR-004) - hybrid structured + natural language
- State schema defined (ADR-012) with agent_outputs namespacing
- Orchestrator pattern defined (ADR-015) with node structure

**What Needs Decision:**
- Prompt engineering strategy for each agent
- Structured output extraction approach
- Confidence scoring methodology
- Model selection per agent (Sonnet vs Haiku)
- Error handling and fallback strategies
- Testing approach for agent logic
- Prompt versioning and iteration

### Requirements

**Functional Requirements:**
1. **NL Parser Agent**: Extract structured event data from natural language
2. **Scheduling Agent**: Find optimal time slots based on constraints
3. **Resource Manager Agent**: Check resource availability and capacity
4. **Conflict Detection Agent**: Identify scheduling conflicts
5. **Resolution Agent**: Generate conflict resolution strategies
6. **Query Agent**: Answer natural language questions about schedule

**Non-Functional Requirements:**
1. **Reliability**: Agents return valid structured output ≥95% of time
2. **Performance**: Agent execution < 2s (p95) including LLM call
3. **Accuracy**: High confidence predictions correct ≥90% of time
4. **Consistency**: Same input produces deterministic output structure
5. **Debuggability**: Clear error messages when parsing fails

**Output Requirements (ADR-004):**
All agents must return:
```python
{
    "data": dict,           # Structured output specific to agent
    "confidence": float,    # 0.0-1.0 confidence score
    "explanation": str,     # User-facing summary
    "reasoning": str        # Why this conclusion was reached
}
```

## Decision

We will implement each agent following a **standardized pattern** with the following architectural decisions:

### 1. Standardized Agent Function Pattern

**Decision:** All agents follow a consistent implementation template.

**Agent Template:**

```python
from typing import Dict, Any
from src.agents.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Define agent-specific output schema
class NLParserOutput(BaseModel):
    """Structured output from NL Parser agent."""
    event_type: Literal["create", "modify", "cancel", "query"]
    title: Optional[str] = None
    start_time: Optional[str] = None  # ISO 8601
    end_time: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)
    priority: Optional[Literal["low", "medium", "high"]] = None
    recurrence_rule: Optional[str] = None
    flexibility: Optional[Literal["fixed", "flexible", "very_flexible"]] = None

def invoke_nl_parser_agent(
    llm,
    user_input: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    NL Parser Agent: Extract structured event data from natural language.

    Args:
        llm: Language model instance
        user_input: Natural language input from user
        context: Additional context (family members, resources, history)

    Returns:
        Agent output dict with data, confidence, explanation, reasoning
    """
    try:
        # 1. Set up output parser
        output_parser = PydanticOutputParser(pydantic_object=NLParserOutput)

        # 2. Build prompt
        prompt = build_nl_parser_prompt(user_input, context, output_parser)

        # 3. Invoke LLM
        chain = prompt | llm | output_parser
        parsed_output = chain.invoke({
            "user_input": user_input,
            "context": format_context(context)
        })

        # 4. Calculate confidence
        confidence = calculate_nl_confidence(parsed_output, user_input, context)

        # 5. Generate explanation and reasoning
        explanation = generate_nl_explanation(parsed_output)
        reasoning = generate_nl_reasoning(parsed_output, user_input, confidence)

        # 6. Return standardized output
        return {
            "data": parsed_output.model_dump(),
            "confidence": confidence,
            "explanation": explanation,
            "reasoning": reasoning
        }

    except ValidationError as e:
        # LLM returned invalid structure
        logger.error(f"NL Parser validation error: {e}")
        return fallback_nl_parser(user_input, context)

    except Exception as e:
        # LLM call failed
        logger.error(f"NL Parser invocation error: {e}", exc_info=True)
        raise

def build_nl_parser_prompt(
    user_input: str,
    context: Dict[str, Any],
    output_parser: PydanticOutputParser
) -> ChatPromptTemplate:
    """Build prompt for NL Parser agent."""
    return ChatPromptTemplate.from_messages([
        ("system", """You are an expert at understanding natural language requests about scheduling events.

Your task: Extract structured event data from the user's input.

{format_instructions}

Context Information:
- Family members: {family_members}
- Available resources: {resources}
- Today's date: {today}

Guidelines:
1. Infer reasonable defaults when information is missing
2. Use ISO 8601 format for dates/times
3. Set event_type based on intent (create, modify, cancel, query)
4. Include all mentioned participants and resources
5. For recurring events, use RRULE format
6. Mark time as None if not specified

Be precise but not overly verbose."""),
        ("user", "{user_input}")
    ])

def calculate_nl_confidence(
    parsed_output: NLParserOutput,
    user_input: str,
    context: Dict[str, Any]
) -> float:
    """
    Calculate confidence score for NL parsing.

    Confidence factors:
    - Time specified explicitly: +0.3
    - Title is clear: +0.2
    - Participants mentioned: +0.2
    - Resources specified: +0.1
    - Date is explicit (not relative): +0.2
    - Input length > 10 words: +0.1 (more context)

    Base confidence: 0.5
    """
    confidence = 0.5

    # Explicit time specified
    if parsed_output.start_time and is_explicit_time(user_input):
        confidence += 0.3

    # Clear title
    if parsed_output.title and len(parsed_output.title) > 3:
        confidence += 0.2

    # Participants mentioned
    if len(parsed_output.participants) > 0:
        confidence += 0.2

    # Resources specified
    if len(parsed_output.resources) > 0:
        confidence += 0.1

    # Explicit date (not "next Saturday")
    if parsed_output.start_time and not has_relative_date_reference(user_input):
        confidence += 0.2

    # More context = higher confidence
    word_count = len(user_input.split())
    if word_count > 10:
        confidence += 0.1

    return min(confidence, 1.0)

def generate_nl_explanation(parsed_output: NLParserOutput) -> str:
    """Generate user-facing explanation."""
    event_type = parsed_output.event_type
    title = parsed_output.title or "event"

    if event_type == "create":
        time_str = (
            f" on {format_time(parsed_output.start_time)}"
            if parsed_output.start_time
            else ""
        )
        return f"Creating '{title}'{time_str}"

    elif event_type == "query":
        return f"Answering question about: {title}"

    elif event_type == "modify":
        return f"Modifying event: {title}"

    else:  # cancel
        return f"Canceling event: {title}"

def generate_nl_reasoning(
    parsed_output: NLParserOutput,
    user_input: str,
    confidence: float
) -> str:
    """Generate reasoning explanation."""
    reasons = []

    if confidence > 0.8:
        reasons.append("High confidence due to clear and explicit input")
    elif confidence < 0.6:
        reasons.append("Lower confidence - some details ambiguous")

    if parsed_output.start_time:
        reasons.append("Time reference detected")
    else:
        reasons.append("No specific time mentioned")

    if len(parsed_output.participants) > 0:
        reasons.append(f"{len(parsed_output.participants)} participant(s) identified")

    return "; ".join(reasons)

def fallback_nl_parser(user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback when LLM output is invalid.

    Return low confidence with partial data.
    """
    logger.warning("Using fallback NL parser")

    return {
        "data": {
            "event_type": "create",
            "title": user_input[:50],  # Use input as title
            "start_time": None,
            "end_time": None,
            "participants": [],
            "resources": [],
            "priority": None,
            "recurrence_rule": None,
            "flexibility": None
        },
        "confidence": 0.3,  # Low confidence
        "explanation": "Unable to fully parse input - need clarification",
        "reasoning": "LLM output validation failed, using fallback"
    }
```

**Key Pattern Elements:**
1. **Pydantic output schema** - Validates LLM response structure
2. **Prompt builder** - Separates prompt construction
3. **Confidence calculator** - Rule-based scoring
4. **Explanation generators** - User-facing and debugging text
5. **Fallback handler** - Graceful degradation
6. **Error handling** - Try/catch with specific error types

---

### 2. Model Selection Strategy: Sonnet vs Haiku

**Decision:** Use Claude Sonnet 4 for complex agents, Claude Haiku for simple agents.

**Model Assignment:**

| Agent | Model | Rationale |
|-------|-------|-----------|
| **NL Parser** | Sonnet | Complex natural language understanding, ambiguity resolution |
| **Scheduling** | Sonnet | Constraint optimization, preference balancing |
| **Resource Manager** | Haiku | Simple capacity checking, deterministic logic |
| **Conflict Detection** | Haiku | Pattern matching, overlap detection |
| **Resolution** | Sonnet | Creative problem solving, strategy generation |
| **Query** | Sonnet | Natural language understanding, context retrieval |

**Implementation:**

```python
from src.agents.llm import get_llm

def get_agent_llm(agent_name: str):
    """Get appropriate LLM for agent."""

    # Complex agents use Sonnet
    if agent_name in ["nl_parser", "scheduling", "resolution", "query"]:
        return get_llm(model="sonnet")

    # Simple agents use Haiku (faster, cheaper)
    else:  # resource_manager, conflict_detection
        return get_llm(model="haiku")
```

**Cost/Performance Tradeoff:**
- Sonnet: ~$3 per 1M input tokens, ~800ms latency
- Haiku: ~$0.25 per 1M input tokens, ~400ms latency
- Mixed approach: 40% cost reduction vs all-Sonnet

---

### 3. Prompt Engineering Strategy

**Decision:** Use system/user message split with format instructions and examples.

**Prompt Structure:**

```python
ChatPromptTemplate.from_messages([
    ("system", """
    [Role Definition]
    You are an expert at [specific task].

    [Task Description]
    Your task: [what the agent does]

    [Output Format]
    {format_instructions}  # From PydanticOutputParser

    [Context]
    - Context item 1: {context_var_1}
    - Context item 2: {context_var_2}

    [Guidelines]
    1. Guideline 1
    2. Guideline 2
    3. Guideline 3

    [Quality Criteria]
    - Criterion 1
    - Criterion 2
    """),
    ("user", "{user_input}")
])
```

**Prompt Engineering Principles:**

1. **Role First**: Start with clear role definition
2. **Task Explicit**: State exactly what output is expected
3. **Format Strict**: Use PydanticOutputParser format instructions
4. **Context Relevant**: Include only necessary context
5. **Guidelines Clear**: Numbered list of rules
6. **Examples Optional**: Include for complex tasks
7. **Tone Professional**: Avoid conversational fluff

**Example: Scheduling Agent Prompt**

```python
ChatPromptTemplate.from_messages([
    ("system", """You are an expert scheduling assistant specialized in finding optimal time slots.

Your task: Analyze the requested event and available time windows, then propose the best time slot considering:
- Participant availability
- Resource availability
- User preferences (morning/afternoon/evening)
- Existing event density (avoid overloading days)

{format_instructions}

Context:
- Requested event: {event_request}
- Available time windows: {time_windows}
- Participant schedules: {participant_schedules}
- Resource schedules: {resource_schedules}
- User preferences: {preferences}

Guidelines:
1. Prioritize explicitly requested times if available
2. Respect hard constraints (participant availability)
3. Consider soft constraints (preferences) with lower weight
4. Propose primary slot + 2 alternative slots
5. Include reasoning for each proposed slot
6. If no slots available, explain why and suggest resolution

Quality Criteria:
- All participants must be available (hard constraint)
- All resources must be available (hard constraint)
- Prefer user's preferred time of day (soft constraint)
- Avoid back-to-back events when possible (soft constraint)
- Balance event distribution across week (soft constraint)
"""),
    ("user", "Find optimal time slot for: {event_title}")
])
```

---

### 4. Structured Output Extraction with Pydantic

**Decision:** Use `PydanticOutputParser` for all structured outputs.

**Implementation Pattern:**

```python
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

# 1. Define output schema
class SchedulingAgentOutput(BaseModel):
    """Output schema for Scheduling Agent."""

    proposed_slot: TimeSlot = Field(
        ...,
        description="Primary recommended time slot"
    )

    alternative_slots: List[TimeSlot] = Field(
        default_factory=list,
        max_length=2,
        description="Up to 2 alternative time slots"
    )

    slot_scores: Dict[str, float] = Field(
        ...,
        description="Score for each slot (0-1)"
    )

    constraints_satisfied: List[str] = Field(
        default_factory=list,
        description="List of satisfied constraints"
    )

    constraints_violated: List[str] = Field(
        default_factory=list,
        description="List of violated soft constraints"
    )

class TimeSlot(BaseModel):
    """Time slot definition."""
    start_time: str = Field(..., description="ISO 8601 start time")
    end_time: str = Field(..., description="ISO 8601 end time")
    reasoning: str = Field(..., description="Why this slot was chosen")

# 2. Create parser
output_parser = PydanticOutputParser(pydantic_object=SchedulingAgentOutput)

# 3. Inject format instructions into prompt
format_instructions = output_parser.get_format_instructions()

# 4. Use in chain
chain = prompt | llm | output_parser
result = chain.invoke(inputs)  # Returns SchedulingAgentOutput instance
```

**Benefits:**
- **Validation**: Pydantic validates LLM output automatically
- **Type Safety**: Returns typed Python objects
- **Documentation**: Schema serves as output documentation
- **Error Handling**: Clear error messages when parsing fails
- **Format Instructions**: Auto-generated JSON schema for LLM

**Fallback on Validation Error:**

```python
try:
    result = chain.invoke(inputs)
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
    # Use fallback with low confidence
    result = create_fallback_result()
```

---

### 5. Confidence Scoring Methodology

**Decision:** Rule-based confidence scoring with agent-specific factors.

**Confidence Calculation Framework:**

```python
def calculate_confidence(
    parsed_output: BaseModel,
    input_data: Dict[str, Any],
    context: Dict[str, Any]
) -> float:
    """
    Calculate confidence score (0.0 - 1.0).

    Approach: Start with base confidence, add/subtract based on factors.
    """
    confidence = BASE_CONFIDENCE  # Agent-specific base (0.5 - 0.7)

    # Factor 1: Input quality
    confidence += assess_input_quality(input_data)  # -0.2 to +0.2

    # Factor 2: Output completeness
    confidence += assess_output_completeness(parsed_output)  # 0.0 to +0.2

    # Factor 3: Context availability
    confidence += assess_context_availability(context)  # 0.0 to +0.1

    # Factor 4: Agent-specific factors
    confidence += agent_specific_factors(parsed_output, input_data)  # varies

    return max(0.0, min(confidence, 1.0))  # Clamp to [0, 1]
```

**Agent-Specific Confidence Factors:**

**NL Parser:**
- Base: 0.5
- Explicit time reference: +0.3
- Clear title: +0.2
- Participants mentioned: +0.2
- Resources specified: +0.1
- Explicit date: +0.2

**Scheduling Agent:**
- Base: 0.7 (deterministic logic)
- All constraints satisfied: +0.3
- Multiple slots available: +0.1
- User preference matched: +0.1
- Some constraints violated: -0.3

**Conflict Detection:**
- Base: 0.95 (highly deterministic)
- Clear time overlap: +0.05
- Resource capacity exceeded: +0.05
- Soft constraint violation: -0.1

**Resolution Agent:**
- Base: 0.6
- Multiple strategies available: +0.2
- All participants accommodated: +0.2
- Minimal impact on other events: +0.1

**Confidence Thresholds:**

```python
# Confidence thresholds for routing
CLARIFICATION_THRESHOLD = 0.7  # Below this → request clarification
HIGH_CONFIDENCE_THRESHOLD = 0.8  # Above this → high confidence
```

---

### 6. Agent-Specific Implementation Details

### 6.1 NL Parser Agent

**Purpose:** Extract structured event data from natural language input.

**Output Schema:**

```python
class NLParserOutput(BaseModel):
    event_type: Literal["create", "modify", "cancel", "query"]
    title: Optional[str] = None
    start_time: Optional[str] = None  # ISO 8601
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    participants: List[str] = []
    resources: List[str] = []
    priority: Optional[Literal["low", "medium", "high"]] = None
    recurrence_rule: Optional[str] = None  # RRULE format
    flexibility: Optional[Literal["fixed", "flexible", "very_flexible"]] = None
    location: Optional[str] = None
    notes: Optional[str] = None
```

**Key Challenges:**
- Ambiguous time references ("next Tuesday", "tomorrow morning")
- Implicit participants ("family dinner" → all family members)
- Recurring event patterns ("every Monday")

**Prompt Strategy:**
- Provide current date/time prominently
- Include family member names in context
- Give examples of time parsing
- Request explicit "None" for missing fields

---

### 6.2 Scheduling Agent

**Purpose:** Find optimal time slots for events based on constraints.

**Output Schema:**

```python
class SchedulingOutput(BaseModel):
    proposed_slot: TimeSlot
    alternative_slots: List[TimeSlot] = []
    slot_scores: Dict[str, float]  # slot_id → score
    constraints_satisfied: List[str]
    constraints_violated: List[str]
    optimization_rationale: str

class TimeSlot(BaseModel):
    start_time: str  # ISO 8601
    end_time: str
    score: float  # 0-1
    reasoning: str
```

**Key Challenges:**
- Multi-constraint optimization
- Balancing hard vs soft constraints
- Handling "no slots available" gracefully

**Prompt Strategy:**
- Explicitly list hard constraints (must satisfy)
- List soft constraints with priorities
- Request multiple alternative slots
- Ask for reasoning per slot

**Model:** Sonnet (complex optimization)

---

### 6.3 Resource Manager Agent

**Purpose:** Check resource availability and capacity.

**Output Schema:**

```python
class ResourceManagerOutput(BaseModel):
    resources_checked: List[ResourceCheck]
    all_available: bool
    conflicts: List[ResourceConflict]
    recommendations: List[str]

class ResourceCheck(BaseModel):
    resource_id: str
    resource_name: str
    requested_capacity: int
    available_capacity: int
    is_available: bool
    time_range: TimeRange

class ResourceConflict(BaseModel):
    resource_id: str
    conflict_type: Literal["unavailable", "over_capacity", "maintenance"]
    conflicting_event_ids: List[str]
    suggestion: str
```

**Key Challenges:**
- Capacity management (e.g., car seats 5 people)
- Time range overlap checking
- Multiple resource conflicts

**Prompt Strategy:**
- Provide clear capacity numbers
- Show existing bookings for time range
- Request specific conflict identification

**Model:** Haiku (deterministic capacity checking)

---

### 6.4 Conflict Detection Agent

**Purpose:** Identify scheduling conflicts and constraint violations.

**Output Schema:**

```python
class ConflictDetectionOutput(BaseModel):
    has_conflicts: bool
    conflicts: List[Conflict]
    severity: Literal["none", "low", "medium", "high"]
    summary: str

class Conflict(BaseModel):
    conflict_id: str
    conflict_type: Literal[
        "time_overlap",
        "resource_unavailable",
        "participant_unavailable",
        "hard_constraint_violation",
        "soft_constraint_violation"
    ]
    severity: Literal["low", "medium", "high"]
    description: str
    affected_entities: List[str]  # participant IDs, resource IDs
    conflicting_event_id: Optional[str]
    constraint_violated: Optional[str]
```

**Key Challenges:**
- Distinguishing hard vs soft constraint violations
- Prioritizing conflicts by severity
- Identifying root cause of conflicts

**Prompt Strategy:**
- Provide complete event details
- Show overlapping events explicitly
- Request severity classification

**Model:** Haiku (pattern matching)

---

### 6.5 Resolution Agent

**Purpose:** Generate conflict resolution strategies.

**Output Schema:**

```python
class ResolutionOutput(BaseModel):
    proposed_resolutions: List[Resolution]
    recommended_resolution_id: str
    cannot_resolve: bool
    cannot_resolve_reason: Optional[str]

class Resolution(BaseModel):
    resolution_id: str
    strategy: Literal[
        "move_new_event",
        "move_existing_event",
        "cancel_conflicting",
        "split_event",
        "change_resource",
        "remove_participant"
    ]
    description: str
    score: float  # 0-1, desirability
    impact: Literal["low", "medium", "high"]
    affected_events: List[str]
    new_time_slot: Optional[TimeSlot]
    trade_offs: List[str]
```

**Key Challenges:**
- Creative problem solving
- Balancing multiple trade-offs
- Prioritizing low-impact solutions

**Prompt Strategy:**
- Describe conflicts in detail
- Request multiple strategies
- Ask for impact assessment
- Request scoring with rationale

**Model:** Sonnet (creative problem solving)

---

### 6.6 Query Agent

**Purpose:** Answer natural language questions about schedule.

**Output Schema:**

```python
class QueryOutput(BaseModel):
    query_type: Literal[
        "availability",
        "event_lookup",
        "schedule_summary",
        "what_if",
        "general"
    ]
    answer: str  # Natural language answer
    supporting_data: Dict[str, Any]  # Relevant events, time slots, etc.
    confidence: float
    sources: List[str]  # Event IDs, resource IDs referenced

class AvailabilityResult(BaseModel):
    """For availability queries."""
    available_slots: List[TimeSlot]
    busy_slots: List[TimeSlot]
    participants_checked: List[str]
```

**Key Challenges:**
- Understanding diverse query types
- Retrieving relevant data efficiently
- Formatting natural language responses

**Prompt Strategy:**
- Include relevant schedule data in context
- Request structured supporting data
- Ask for sources (traceable)

**Model:** Sonnet (natural language understanding)

---

### 7. Error Handling and Fallback Strategies

**Decision:** Multi-level fallback hierarchy with graceful degradation.

**Error Handling Levels:**

**Level 1: Retry with Validation Error Feedback**

```python
def invoke_agent_with_retry(
    agent_fn,
    inputs: Dict[str, Any],
    max_retries: int = 2
) -> Dict[str, Any]:
    """Retry agent invocation on validation errors."""

    for attempt in range(max_retries):
        try:
            result = agent_fn(**inputs)
            return result
        except ValidationError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Validation error, retry {attempt+1}: {e}")
                # Include error in context for next attempt
                inputs["previous_error"] = str(e)
                continue
            else:
                logger.error(f"Max retries exceeded: {e}")
                return create_fallback_result(inputs, error=e)
```

**Level 2: Fallback with Partial Data**

```python
def create_fallback_result(
    inputs: Dict[str, Any],
    error: Exception
) -> Dict[str, Any]:
    """Create low-confidence fallback result."""

    return {
        "data": create_minimal_output(inputs),
        "confidence": 0.3,  # Low confidence
        "explanation": "Unable to fully process - using fallback",
        "reasoning": f"Error: {str(error)}, partial output generated"
    }
```

**Level 3: Propagate Error to Orchestrator**

```python
def invoke_agent_safe(agent_fn, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Safely invoke agent, never raise exceptions."""

    try:
        return invoke_agent_with_retry(agent_fn, inputs)
    except LLMError as e:
        logger.error(f"LLM error: {e}")
        return {
            "data": {},
            "confidence": 0.0,
            "explanation": "Service temporarily unavailable",
            "reasoning": "LLM API error",
            "error": {
                "type": "llm_error",
                "message": str(e),
                "retryable": True
            }
        }
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return {
            "data": {},
            "confidence": 0.0,
            "explanation": "Unexpected error occurred",
            "reasoning": "Internal error",
            "error": {
                "type": "agent_failure",
                "message": str(e),
                "retryable": False
            }
        }
```

---

### 8. Testing Strategy for Agents

**Decision:** Test agents independently from orchestrator with mocked LLMs.

**Testing Levels:**

**Level 1: Unit Tests with Mocked LLM**

```python
# tests/unit/test_agents/test_nl_parser.py
from src.agents.nl_parser import invoke_nl_parser_agent
from unittest.mock import Mock

def test_nl_parser_high_confidence():
    """Test NL parser with clear input."""

    # Mock LLM to return specific output
    mock_llm = Mock()
    mock_llm.invoke.return_value = {
        "event_type": "create",
        "title": "Soccer practice",
        "start_time": "2026-01-11T14:00:00Z",
        "participants": ["child_1", "parent_1"]
    }

    result = invoke_nl_parser_agent(
        llm=mock_llm,
        user_input="Schedule soccer practice Saturday at 2pm",
        context={"family_members": ["child_1", "parent_1"]}
    )

    assert result["confidence"] > 0.8
    assert result["data"]["event_type"] == "create"
    assert result["data"]["title"] == "Soccer practice"

def test_nl_parser_low_confidence():
    """Test NL parser with ambiguous input."""

    mock_llm = Mock()
    mock_llm.invoke.return_value = {
        "event_type": "create",
        "title": "meeting",
        "start_time": None,  # Ambiguous time
        "participants": []
    }

    result = invoke_nl_parser_agent(
        llm=mock_llm,
        user_input="Schedule a meeting next week",
        context={}
    )

    assert result["confidence"] < 0.7
```

**Level 2: Integration Tests with Real LLM**

```python
# tests/integration/test_agents/test_nl_parser_integration.py
from src.agents.nl_parser import invoke_nl_parser_agent
from src.agents.llm import get_llm

@pytest.mark.integration
def test_nl_parser_real_llm():
    """Test NL parser with real LLM (requires API key)."""

    llm = get_llm(model="sonnet")

    result = invoke_nl_parser_agent(
        llm=llm,
        user_input="Schedule dentist appointment next Tuesday at 3pm",
        context={
            "today": "2026-01-11",
            "family_members": ["parent_1", "child_1"]
        }
    )

    # Verify structure
    assert "data" in result
    assert "confidence" in result
    assert "explanation" in result
    assert "reasoning" in result

    # Verify parsing accuracy
    assert result["data"]["event_type"] == "create"
    assert "dentist" in result["data"]["title"].lower()
    assert result["data"]["start_time"] is not None
```

**Level 3: Prompt Evaluation Tests**

```python
# tests/evaluation/test_nl_parser_accuracy.py
import pytest

@pytest.mark.parametrize("input_text,expected_event_type,expected_confidence", [
    ("Schedule soccer Saturday at 2pm", "create", 0.9),
    ("Cancel my dentist appointment", "cancel", 0.85),
    ("When am I free tomorrow?", "query", 0.8),
    ("Move the meeting to later", "modify", 0.75),
    ("Schedule something next week", "create", 0.5),  # Low confidence
])
def test_nl_parser_accuracy(input_text, expected_event_type, expected_confidence):
    """Test NL parser accuracy across various inputs."""

    llm = get_llm()
    result = invoke_nl_parser_agent(llm, input_text, {})

    assert result["data"]["event_type"] == expected_event_type
    assert abs(result["confidence"] - expected_confidence) < 0.2
```

---

### 9. Prompt Versioning and Iteration

**Decision:** Version prompts in code with changelog, enable A/B testing.

**Versioning Strategy:**

```python
# src/agents/prompts/nl_parser_prompts.py

NL_PARSER_PROMPT_V1 = ChatPromptTemplate.from_messages([...])  # Initial version

NL_PARSER_PROMPT_V2 = ChatPromptTemplate.from_messages([...])  # Improved version

# Active version (configurable)
ACTIVE_NL_PARSER_PROMPT = NL_PARSER_PROMPT_V2

def get_nl_parser_prompt(version: Optional[str] = None) -> ChatPromptTemplate:
    """Get NL parser prompt, optionally specific version."""

    if version == "v1":
        return NL_PARSER_PROMPT_V1
    elif version == "v2":
        return NL_PARSER_PROMPT_V2
    else:
        return ACTIVE_NL_PARSER_PROMPT

# Prompt changelog
"""
# NL Parser Prompt Changelog

## v2 (2026-01-11)
- Added explicit date format instructions
- Included family member context in system message
- Improved time parsing guidelines
- Result: +15% confidence, +10% accuracy

## v1 (2026-01-08)
- Initial implementation
- Basic role + task + format instructions
"""
```

**A/B Testing Support:**

```python
def invoke_agent_with_ab_test(
    agent_fn,
    inputs: Dict[str, Any],
    prompt_versions: List[str],
    experiment_id: str
) -> Dict[str, Any]:
    """Test multiple prompt versions in parallel."""

    results = []
    for version in prompt_versions:
        result = agent_fn(**inputs, prompt_version=version)
        result["prompt_version"] = version
        results.append(result)

    # Log for analysis
    log_ab_test_results(experiment_id, results)

    # Return primary version result
    return results[0]
```

---

## Consequences

### Positive

1. **Consistent Implementation**: Standardized pattern makes all agents predictable
2. **Type Safety**: Pydantic schemas prevent invalid outputs
3. **Cost Optimized**: Haiku for simple tasks reduces costs 40%
4. **Testable**: Agents testable independently with mocked LLMs
5. **Observable**: Confidence scores enable routing decisions
6. **Maintainable**: Prompts versioned and documented
7. **Reliable**: Fallback strategies prevent total failures
8. **Debuggable**: Clear error messages and reasoning

### Negative

1. **Prompt Engineering Time**: Crafting effective prompts requires iteration
2. **Validation Overhead**: Pydantic parsing adds 10-20ms latency
3. **LLM Dependency**: Quality depends on LLM performance
4. **Testing Cost**: Integration tests with real LLM consume API credits
5. **Complexity**: 6 agents × multiple versions = maintenance burden

### Mitigations

1. **Prompt Engineering**: Start with templates, iterate based on test results
2. **Validation Overhead**: Acceptable for reliability gains
3. **LLM Dependency**: Fallback strategies handle failures gracefully
4. **Testing Cost**: Use mocked LLMs for unit tests, real LLM for subset
5. **Complexity**: Clear documentation and standardized patterns reduce burden

## Alternatives Considered

### Alternative 1: No Structured Outputs (Free-Form Text)

**Pros:**
- Simpler prompts
- No validation needed
- More flexible

**Cons:**
- Unreliable parsing
- Hard to extract structured data
- No type safety
- Difficult to test

**Decision:** Rejected - Structured outputs essential for reliability

### Alternative 2: Single Model for All Agents (All Sonnet)

**Pros:**
- Simpler configuration
- Consistent performance
- Higher quality outputs

**Cons:**
- 2.5x higher cost
- Slower execution for simple tasks
- Wasteful for deterministic agents

**Decision:** Rejected - Cost optimization important

### Alternative 3: Function Calling Instead of Output Parsing

**Pros:**
- Native LLM feature
- More reliable than parsing
- Better for tool use

**Cons:**
- Not all models support it consistently
- Less control over output shape
- Harder to version

**Decision:** Rejected - Pydantic parsing more flexible

### Alternative 4: Zero-Shot Prompts (No Examples)

**Pros:**
- Shorter prompts
- Faster execution
- Less token usage

**Cons:**
- Lower accuracy
- Higher variance
- Less reliable outputs

**Decision:** Accepted - Start zero-shot, add examples if needed

### Alternative 5: Single Agent (No Specialization)

**Pros:**
- Simpler architecture
- One prompt to maintain
- Less coordination

**Cons:**
- Violates hub-and-spoke (ADR-002)
- Lower quality per task
- Harder to optimize
- Less observable

**Decision:** Rejected - Specialization core to architecture

## Implementation

### Implementation Plan

**Phase 1: Agent Scaffolding**
1. Create `src/agents/` directory structure
2. Implement base agent template in `src/agents/base.py`
3. Create output schemas for all 6 agents
4. Set up LLM model selection utility

**Phase 2: Core Agents (NL Parser, Conflict Detection)**
1. Implement NL Parser agent with prompts
2. Implement Conflict Detection agent
3. Write unit tests with mocked LLMs
4. Write integration tests with real LLM

**Phase 3: Advanced Agents (Scheduling, Resolution)**
1. Implement Scheduling agent
2. Implement Resolution agent
3. Write unit and integration tests
4. Tune confidence scoring

**Phase 4: Supporting Agents (Resource Manager, Query)**
1. Implement Resource Manager agent
2. Implement Query agent
3. Write comprehensive tests
4. Document prompt versions

**Phase 5: Optimization**
1. Run accuracy evaluation tests
2. Iterate on prompts based on results
3. Tune confidence thresholds
4. Optimize fallback strategies

### Testing Strategy

**Unit Tests (90% coverage):**
- Test each agent function with mocked LLM
- Test confidence calculation logic
- Test fallback handlers
- Test error cases

**Integration Tests:**
- Test agents with real LLM (subset of inputs)
- Verify output structure
- Measure latency and cost

**Evaluation Tests:**
- Parametrized tests with diverse inputs
- Measure accuracy and confidence correlation
- Compare prompt versions

### Performance Targets

| Agent | Model | Target Latency (p95) | Target Accuracy |
|-------|-------|---------------------|-----------------|
| NL Parser | Sonnet | 2s | 90% |
| Scheduling | Sonnet | 2.5s | 85% |
| Resource Manager | Haiku | 1s | 95% |
| Conflict Detection | Haiku | 1s | 98% |
| Resolution | Sonnet | 2.5s | 80% |
| Query | Sonnet | 2s | 85% |

### Critical Files

**New Files:**
- `src/agents/__init__.py` - Agent exports
- `src/agents/base.py` - Base agent template
- `src/agents/nl_parser.py` - NL Parser implementation
- `src/agents/scheduling.py` - Scheduling agent
- `src/agents/resource_manager.py` - Resource Manager
- `src/agents/conflict_detection.py` - Conflict Detection
- `src/agents/resolution.py` - Resolution agent
- `src/agents/query.py` - Query agent
- `src/agents/prompts/` - Prompt templates directory
- `src/agents/schemas.py` - Pydantic output schemas

**Test Files:**
- `tests/unit/test_agents/` - Unit tests for each agent
- `tests/integration/test_agents/` - Integration tests
- `tests/evaluation/test_agent_accuracy.py` - Accuracy evaluation

### Related ADRs

- **ADR-002**: Hub-and-Spoke Agent Architecture - Agents coordinated by orchestrator
- **ADR-004**: Hybrid Agent Output Format - All agents return data + explanation
- **ADR-011**: LLM Provider Selection - Claude Sonnet/Haiku usage
- **ADR-012**: LangGraph State Schema - Agent outputs stored in state
- **ADR-015**: Orchestrator Implementation - Agents invoked by orchestrator nodes

---

**Last Updated**: 2026-01-11
**Status**: Accepted, awaiting implementation
