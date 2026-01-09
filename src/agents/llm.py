"""
LLM initialization and configuration for Family Scheduler agents.

This module provides centralized LLM instance creation and model selection
for all agents in the system. Uses Anthropic Claude as the primary provider.
"""

from langchain_anthropic import ChatAnthropic

from src.config import get_settings

# Model constants for Anthropic Claude
SONNET_MODEL = "claude-sonnet-4-20250514"  # Claude Sonnet 4 (current version)
HAIKU_MODEL = "claude-3-haiku-20240307"
OPUS_MODEL = "claude-opus-4-5-20251101"  # Claude Opus 4.5 (latest)

# Model selection by use case
DEFAULT_MODEL = SONNET_MODEL  # Primary model for most agents
FAST_MODEL = HAIKU_MODEL  # Fast model for simple queries
COMPLEX_MODEL = OPUS_MODEL  # Reserved for complex scenarios


def get_llm(
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    streaming: bool = False,
) -> ChatAnthropic:
    """
    Get configured Anthropic Claude LLM instance.

    This is the primary function for creating LLM instances across all agents.
    It handles API key loading, model selection, and common configuration.

    Args:
        model: Model name. If None, uses DEFAULT_MODEL (Claude Sonnet 4).
               Use HAIKU_MODEL for faster/cheaper queries or OPUS_MODEL for
               complex tasks requiring maximum reasoning capability.
        temperature: Sampling temperature (0.0-1.0). Lower values make output
                    more deterministic. Default 0.7 balances creativity and
                    consistency.
        max_tokens: Maximum tokens in the response. Default 4096 is sufficient
                   for most agent responses. Reduce for cost savings.
        streaming: Enable streaming responses. Useful for UI implementations
                  but not needed for agent-to-agent communication.

    Returns:
        Configured ChatAnthropic instance ready for use with LangChain/LangGraph

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not configured in environment

    Examples:
        >>> # Use default Sonnet model for agent
        >>> llm = get_llm()
        >>> response = llm.invoke("What is the capital of France?")

        >>> # Use Haiku for faster, cheaper queries
        >>> fast_llm = get_llm(model=HAIKU_MODEL)
        >>> quick_response = fast_llm.invoke("Parse: 'meeting at 2pm'")

        >>> # Use lower temperature for more deterministic outputs
        >>> deterministic_llm = get_llm(temperature=0.1)
        >>> structured_output = deterministic_llm.invoke(prompt)

        >>> # Enable streaming for future UI
        >>> streaming_llm = get_llm(streaming=True)
        >>> for chunk in streaming_llm.stream("Tell me a story"):
        ...     print(chunk.content, end="", flush=True)
    """
    settings = get_settings()
    api_key = settings.get_llm_api_key()  # Validates key exists

    return ChatAnthropic(
        model=model or DEFAULT_MODEL,
        anthropic_api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
    )


def get_sonnet_llm(**kwargs) -> ChatAnthropic:
    """
    Get Claude Sonnet 4 LLM instance (primary model).

    This is a convenience function that explicitly uses Sonnet.
    Use this for standard agent operations where you want to be explicit
    about model selection.

    Args:
        **kwargs: Additional arguments passed to get_llm()

    Returns:
        ChatAnthropic instance configured with Sonnet model

    Example:
        >>> llm = get_sonnet_llm(temperature=0.5)
    """
    return get_llm(model=SONNET_MODEL, **kwargs)


def get_haiku_llm(**kwargs) -> ChatAnthropic:
    """
    Get Claude 3 Haiku LLM instance (fast model).

    Use this for simple queries, quick iterations during development,
    or when speed/cost is more important than maximum reasoning capability.

    Good for:
    - Query Agent (simple availability queries)
    - Development/testing iterations
    - Simple parsing tasks

    Args:
        **kwargs: Additional arguments passed to get_llm()

    Returns:
        ChatAnthropic instance configured with Haiku model

    Example:
        >>> fast_llm = get_haiku_llm()
        >>> result = fast_llm.invoke("Quick parse: meeting tomorrow 2pm")
    """
    return get_llm(model=HAIKU_MODEL, **kwargs)


def get_opus_llm(**kwargs) -> ChatAnthropic:
    """
    Get Claude Opus 4.5 LLM instance (complex model - use sparingly).

    This is the most capable but also most expensive model. Reserve for
    scenarios where Sonnet proves insufficient, such as:
    - Extremely complex conflict resolution
    - Novel scheduling scenarios requiring deep reasoning
    - Cases where Sonnet fails to produce correct outputs

    Cost: Significantly more expensive than Sonnet

    Args:
        **kwargs: Additional arguments passed to get_llm()

    Returns:
        ChatAnthropic instance configured with Opus model

    Example:
        >>> # Only use when Sonnet insufficient
        >>> complex_llm = get_opus_llm(temperature=0.3)
        >>> result = complex_llm.invoke(very_complex_resolution_prompt)
    """
    return get_llm(model=OPUS_MODEL, **kwargs)
