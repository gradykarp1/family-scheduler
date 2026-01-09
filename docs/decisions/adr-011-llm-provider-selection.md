# ADR-011: LLM Provider Selection

## Status
Implemented

**Implementation Status**: Implemented
**Implementation Date**: 2026-01-08

## Context

The Family Scheduler uses multiple specialized AI agents to handle natural language event creation, smart scheduling, conflict detection, and resolution. Each agent requires a Large Language Model (LLM) to perform its reasoning and decision-making tasks.

### Requirements for LLM Provider

**Agent Requirements:**
The system includes six specialized agents, each with specific LLM needs:
- **NL Parser Agent**: Extract structured data from natural language input
- **Scheduling Agent**: Find optimal time slots based on complex constraints
- **Resource Manager Agent**: Check availability and manage capacity
- **Conflict Detection Agent**: Identify and categorize scheduling conflicts
- **Resolution Agent**: Generate intelligent conflict resolution strategies
- **Query Agent**: Answer natural language questions about schedules

**Technical Requirements:**
- Strong reasoning capabilities for multi-step agent workflows
- Ability to produce structured outputs (JSON) reliably
- Good performance with prompt engineering patterns
- Support for function/tool calling (optional but beneficial)
- Large context window for conversation history
- Integration with LangChain/LangGraph ecosystem

**Project Requirements:**
- Cost-effective for learning project (many API calls during development)
- Good documentation and examples for learning
- Observability and debugging support (LangSmith compatibility)
- Reasonable rate limits for development workload
- Fast response times for good developer experience

**Phase 1 Considerations:**
- Local development focus (no complex multi-region deployment)
- Single developer usage pattern
- Emphasis on learning agent patterns, not LLM optimization
- Budget-conscious but prioritizes quality for learning

## Decision

We will use **Anthropic Claude** as the primary LLM provider for all agents.

### Model Selection

**Primary Model: Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`)**
- Use for: All primary agent workflows (Orchestrator, NL Parser, Scheduling, Conflict Detection, Resolution)
- Context window: 200K tokens
- Output: Up to 8K tokens
- Pricing: $3 per million input tokens, $15 per million output tokens
- Strengths: Excellent reasoning, strong at structured outputs, good cost/performance balance

**Fast Model: Claude 3 Haiku (`claude-3-haiku-20240307`)**
- Use for: Simple queries, Query Agent, rapid iterations during development
- Context window: 200K tokens
- Output: Up to 4K tokens
- Pricing: $0.25 per million input tokens, $1.25 per million output tokens
- Strengths: Very fast responses, cost-effective for simple tasks

**Complex Model: Claude 3 Opus (`claude-3-opus-20240229`)** (Reserved)
- Use for: Complex resolution scenarios if Sonnet proves insufficient
- Context window: 200K tokens
- Output: Up to 4K tokens
- Pricing: $15 per million input tokens, $75 per million output tokens
- Strengths: Highest reasoning capability, best for extremely complex tasks

### Cost Controls

**Token Limits:**
- Default max output tokens: 4096 per request
- Monitor and adjust based on actual usage patterns
- Use Haiku for development iterations to reduce costs

**Rate Limiting:**
- Rely on Anthropic SDK's built-in retry logic with exponential backoff
- Implement application-level request queuing if needed
- Phase 1: Single user, rate limits not a concern

**Budget Tracking:**
- Enable LangSmith tracing to monitor token usage
- Set up cost alerts through Anthropic console
- Target: ~$20-50/month for active development
- Estimated: 100-200 agent workflows per week during development

**Development Strategies:**
- Use Claude 3 Haiku for prompt iteration and testing
- Switch to Sonnet only when prompt is stable
- Cache common prompts when possible
- Minimize unnecessary context in prompts

### Integration Approach

**LangChain Integration:**
```python
from langchain_anthropic import ChatAnthropic

# Primary agent model
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    anthropic_api_key=api_key,
    temperature=0.7,
    max_tokens=4096
)
```

**Model Selection Strategy:**
- Default to Sonnet for all agents initially
- Profile agent performance and cost
- Identify opportunities to use Haiku for simpler agents
- Keep model selection configurable for easy experimentation

**Observability:**
- Use LangSmith for request tracing and debugging
- Log token usage per agent type
- Track average cost per agent workflow
- Monitor latency and optimize prompts

**Streaming:**
- Enable streaming for future UI implementations
- Not needed for Phase 1 (API-only)
- Supported by `langchain-anthropic` when needed

## Consequences

### Positive

1. **Development Alignment**: Using Claude while building with Claude Code creates consistency in development experience and understanding of model capabilities

2. **Cost Effective**: Claude 3.5 Sonnet offers excellent cost/performance ratio (~$3/$15 per million tokens), competitive with GPT-4 Turbo while providing larger context window

3. **Strong Reasoning**: Claude excels at multi-step reasoning tasks, which is essential for agent orchestration and conflict resolution

4. **Large Context Window**: 200K tokens supports long conversation histories, extensive prompt context, and detailed examples

5. **Structured Outputs**: Claude 3.5 is very good at producing reliable JSON outputs, critical for agent-to-orchestrator communication

6. **LangChain Support**: First-class integration with `langchain-anthropic` package provides clean abstraction and good documentation

7. **Model Flexibility**: Can easily switch between Haiku/Sonnet/Opus based on task complexity, optimizing cost vs. performance

8. **Good Documentation**: Anthropic provides clear API docs, prompt engineering guides, and examples

9. **Streaming Support**: Built-in streaming capabilities for future UI enhancements

10. **LangSmith Compatible**: Full observability with LangSmith for debugging and optimization

### Negative

1. **API Dependency**: Requires stable internet connection and Anthropic service availability; no offline mode

2. **Cost Accumulation**: Every agent invocation costs money; need to be mindful during development and testing

3. **Rate Limits**: Subject to Anthropic's rate limiting, though manageable for single-developer learning project

4. **Vendor Lock-in**: Prompts may become Anthropic-specific over time, making it harder to switch providers

5. **No Local Fallback**: Can't run agents without API access (unlike local models)

6. **Learning Curve**: Need to learn Anthropic-specific prompt patterns and best practices

### Mitigation Strategies

**For API Dependency:**
- Keep LangChain abstraction layer to make provider switching easier
- Design agent prompts to be as provider-agnostic as possible
- Maintain OpenAI integration as fallback option (SDK already installed)

**For Cost Management:**
- Implement token usage tracking from day one
- Use Haiku for development iterations
- Set up cost alerts in Anthropic console
- Profile each agent type to identify optimization opportunities

**For Rate Limiting:**
- Implement graceful retry logic with exponential backoff
- Queue requests if rate limits become an issue
- Monitor usage patterns and adjust if needed

**For Vendor Lock-in:**
- Use LangChain's model abstraction consistently
- Avoid Anthropic-specific features unless critical
- Document any provider-specific patterns used
- Keep model selection configurable for easy experimentation

## Alternatives Considered

### OpenAI GPT-4 Turbo (`gpt-4-turbo-preview`)

**Pros:**
- Widely used with extensive community examples
- Excellent function calling capabilities
- Strong reasoning performance
- Large ecosystem of tools and libraries

**Cons:**
- Higher cost: $10/$30 per million tokens vs Claude's $3/$15
- Smaller context window: 128K vs Claude's 200K
- Not used in current development environment

**Why not chosen:**
Cost and context window differences are significant. Claude 3.5 Sonnet offers better value for a learning project, and the 200K context window provides more flexibility for agent workflows.

### OpenAI GPT-3.5 Turbo

**Pros:**
- Very inexpensive: $0.50/$1.50 per million tokens
- Fast response times
- Good for simple tasks

**Cons:**
- Significantly weaker reasoning capabilities
- Less reliable structured outputs
- Not suitable for complex agent orchestration
- May require more prompt engineering effort

**Why not chosen:**
Insufficient reasoning capability for complex agent workflows like conflict resolution and multi-step scheduling. The cost savings aren't worth the reduced quality for a learning project focused on agent patterns.

### Local Models (Ollama with LLaMA 3, Mistral, etc.)

**Pros:**
- No API costs once set up
- Complete privacy and control
- No rate limits
- Works offline

**Cons:**
- Requires significant local compute (GPU preferred)
- Quality significantly lower than Claude 3.5 Sonnet
- Complex setup and maintenance
- Slower inference times on consumer hardware
- Not the focus of this learning project

**Why not chosen:**
This project's learning focus is on agent orchestration patterns with LangGraph, not on running or optimizing local models. Cloud API provides better quality and faster iteration. The cost is acceptable for a learning project.

### Google Gemini Pro

**Pros:**
- Competitive pricing
- Long context window (1M tokens in some versions)
- Good reasoning capabilities

**Cons:**
- Less mature LangChain integration
- Fewer examples and community resources
- Not used in current development environment

**Why not chosen:**
While technically capable, Anthropic has better LangChain integration and more established patterns for agent workflows. Development environment alignment (using Claude Code) provides additional learning value.

### Hybrid Approach (Different Providers for Different Agents)

**Pros:**
- Could optimize cost by using cheaper models for simple agents
- Exposure to multiple provider APIs
- Flexibility to use best model for each task

**Cons:**
- Added complexity in configuration and debugging
- Inconsistent behavior across agents
- More difficult to optimize prompts
- Higher cognitive load during development

**Why not chosen:**
Single provider simplifies development and debugging. Can always add provider diversity later if needed. For learning agent patterns, consistency is more valuable than optimization.

## Implementation Notes

### Model Constants

Define model constants for easy switching:

```python
# src/agents/llm.py

# Primary models
SONNET_MODEL = "claude-3-5-sonnet-20241022"
HAIKU_MODEL = "claude-3-haiku-20240307"
OPUS_MODEL = "claude-3-opus-20240229"

# Model selection by use case
DEFAULT_MODEL = SONNET_MODEL
FAST_MODEL = HAIKU_MODEL
COMPLEX_MODEL = OPUS_MODEL
```

### LLM Factory Function

Centralize LLM initialization:

```python
from langchain_anthropic import ChatAnthropic
from src.config import get_settings

def get_llm(
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    streaming: bool = False
) -> ChatAnthropic:
    """
    Get configured Anthropic Claude LLM instance.

    Args:
        model: Model name (defaults to SONNET_MODEL)
        temperature: Sampling temperature 0.0-1.0
        max_tokens: Maximum tokens in response
        streaming: Enable streaming responses

    Returns:
        Configured ChatAnthropic instance

    Example:
        >>> llm = get_llm()  # Use default Sonnet
        >>> fast_llm = get_llm(model=HAIKU_MODEL)  # Use Haiku for speed
    """
    settings = get_settings()
    api_key = settings.get_llm_api_key()

    return ChatAnthropic(
        model=model or DEFAULT_MODEL,
        anthropic_api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming
    )
```

### Environment Configuration

Already configured in `src/config.py`:
- `llm_provider = "anthropic"` (default)
- `anthropic_api_key` field with validation
- `get_llm_api_key()` method

No code changes needed to configuration!

### Getting API Key

1. Sign up at https://console.anthropic.com/
2. Navigate to API Keys section
3. Create new key for "Family Scheduler Development"
4. Copy key to `.env` file:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

### Cost Estimation

**Typical Agent Workflow:**
- Input: ~1000 tokens (context + prompt)
- Output: ~500 tokens (structured response)
- Cost: $0.011 per workflow with Sonnet
- 100 workflows: ~$1.10

**Development Phase (1 month):**
- Estimated workflows: 200-400
- With iteration/testing: 500-1000 agent calls
- Estimated cost: $10-25/month
- Well within learning project budget

## References

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude Model Pricing](https://www.anthropic.com/api)
- [LangChain Anthropic Integration](https://python.langchain.com/docs/integrations/chat/anthropic)
- [LangSmith Tracing](https://docs.smith.langchain.com/)
- [ADR-001: Agent Framework Selection](./adr-001-agent-framework-selection.md)
- [ADR-010: Python Environment & Package Management](./adr-010-python-environment-package-management.md)

## Implementation

**Implemented**: 2026-01-08

### What Was Created

1. **LLM Helper Module** (`src/agents/llm.py`)
   - Centralized LLM initialization for all agents
   - Model constants: SONNET_MODEL, HAIKU_MODEL, OPUS_MODEL
   - Factory function: `get_llm(model, temperature, max_tokens, streaming)`
   - Convenience functions: `get_sonnet_llm()`, `get_haiku_llm()`, `get_opus_llm()`
   - Comprehensive docstrings with usage examples
   - Integration with `src/config.py` for API key validation

2. **Environment Configuration**
   - Added ANTHROPIC_API_KEY to `.env` file
   - Configuration already present in `src/config.py` from ADR-010
   - API key validation working correctly

3. **Documentation Updates**
   - Added ADR-011 to `docs/decisions/README.md` index
   - Updated README.md with Anthropic API key setup instructions
   - Included cost estimate ($20-50/month for development)
   - Links to Anthropic Console for API key creation

### Deviations from Plan

**Model Version Updates**: The ADR was written with Claude 3.5 Sonnet as the primary model, but during implementation we discovered the model IDs have been updated:

- **Planned**: `claude-3-5-sonnet-20241022` (Claude 3.5 Sonnet)
- **Actual**: `claude-sonnet-4-20250514` (Claude Sonnet 4)

**Reason**: The Claude 3.5 Sonnet model ID specified in the ADR returned a 404 error from the Anthropic API. Testing revealed that Claude Sonnet 4 is now available and is the current recommended model.

**Impact**: This is actually a positive deviation - Claude Sonnet 4 is newer and more capable than Claude 3.5 Sonnet while maintaining similar pricing structure. All architectural decisions and cost considerations remain valid.

**Updated Model Constants**:
```python
SONNET_MODEL = "claude-sonnet-4-20250514"  # Primary model
HAIKU_MODEL = "claude-3-haiku-20240307"    # Fast model (unchanged)
OPUS_MODEL = "claude-opus-4-5-20251101"    # Complex model (updated to Opus 4.5)
```

### Lessons Learned

1. **Model Version Volatility**: LLM model IDs change over time as providers release new versions. The specific date-stamped model IDs in ADRs may become outdated quickly.

2. **Testing is Critical**: Running actual API tests during implementation revealed the model version issue immediately, allowing us to update to current versions.

3. **Centralized Configuration**: Having the `src/agents/llm.py` helper module makes it easy to update model versions in one place rather than scattered throughout agent code.

4. **API Key Validation**: The Pydantic Settings validation in `src/config.py` worked perfectly for ensuring the API key is configured before attempting LLM calls.

5. **Newer is Better**: Claude Sonnet 4 and Opus 4.5 represent improvements over the 3.x series, providing better reasoning capabilities while maintaining the same integration approach.

### Verification

All verification tests passed:

```bash
# API key configured
✓ API key configured

# LLM initialized with correct model
✓ LLM initialized: claude-sonnet-4-20250514

# API call successful
✓ API call successful
Response: Hello there, friend!
```

### Next Steps

1. Begin implementing first agent (NL Parser Agent)
2. Use `get_llm()` or `get_sonnet_llm()` for agent initialization
3. Monitor token usage via LangSmith (optional)
4. Consider using `get_haiku_llm()` for development iterations to reduce costs

### Related Files

- `/src/agents/llm.py` - LLM helper module
- `/.env` - Environment configuration with ANTHROPIC_API_KEY
- `/README.md` - Updated setup instructions
- `/docs/decisions/README.md` - Updated index

---

*Date: 2026-01-08*
*Supersedes: None*
