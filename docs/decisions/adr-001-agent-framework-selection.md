# ADR-001: Agent Framework Selection

## Status
Accepted

## Context

The Family Scheduler project requires an agent-based architecture to handle complex scheduling tasks including natural language parsing, conflict detection, resource management, and intelligent resolution suggestions. We need a framework that can:

1. Orchestrate multiple specialized agents with clear workflow management
2. Maintain state across multi-step agent interactions
3. Provide observability and debugging capabilities for learning purposes
4. Support integration with various LLM providers (OpenAI, Anthropic)
5. Scale from local development to cloud deployment

Several agent frameworks were available at the time of this decision:
- **LangGraph**: Part of the LangChain ecosystem, designed for building stateful multi-agent applications
- **AutoGen**: Microsoft's framework for multi-agent conversations
- **CrewAI**: Framework focused on role-based agent collaboration
- **Custom implementation**: Build our own orchestration layer

Since this project serves dual purposes (learning platform and practical tool), the framework choice impacts both the learning experience and technical capabilities.

## Decision

We will use **LangGraph** (with LangChain utilities) as the agent orchestration framework.

## Consequences

### Positive

1. **Mature Ecosystem**: LangChain/LangGraph has extensive documentation, examples, and community support, making it ideal for learning
2. **State Management**: Built-in state management with checkpointing enables complex workflows and recovery from failures
3. **Observability**: LangSmith integration provides tracing, monitoring, and evaluation tools
4. **Flexibility**: LLM-agnostic design allows switching between OpenAI, Anthropic, and other providers
5. **Graph-Based Workflows**: Explicit graph structure makes agent interactions visible and debuggable
6. **Production-Ready**: Proven in production environments, supports scaling and deployment patterns
7. **Learning Resources**: Abundant tutorials, courses, and examples accelerate learning
8. **Extensibility**: Easy to add custom agents and integrate with external tools

### Negative

1. **Learning Curve**: LangGraph's graph-based approach requires understanding new concepts (nodes, edges, state reducers)
2. **Abstraction Overhead**: Framework abstractions may obscure underlying mechanics for learners
3. **Dependency Weight**: LangChain ecosystem has many dependencies, increasing project complexity
4. **Rapid Evolution**: Fast-moving project means APIs may change, requiring maintenance
5. **Opinionated Structure**: Framework patterns may not match all use cases

### Mitigation Strategies

- Start with simple agent workflows to learn LangGraph fundamentals before building complex orchestration
- Use LangSmith from the beginning to develop observability skills
- Keep agent logic simple and focused; leverage framework for orchestration only
- Pin LangChain/LangGraph versions and test upgrades carefully
- Document framework-specific patterns in architecture docs

## Alternatives Considered

### AutoGen
**Pros**: Strong multi-agent conversation capabilities, Microsoft backing
**Cons**: More focused on conversational agents than workflow orchestration, less mature state management
**Why not chosen**: LangGraph's explicit workflow graphs better match our hub-and-spoke architecture

### CrewAI
**Pros**: Simple role-based agent model, good for task delegation
**Cons**: Less control over workflow structure, smaller community, newer project
**Why not chosen**: LangGraph provides more control and better learning resources

### Custom Implementation
**Pros**: Complete control, no external dependencies, tailored to exact needs
**Cons**: Significant development effort, reinventing solved problems, no community support
**Why not chosen**: Defeats the learning objective of mastering existing agent frameworks

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangSmith](https://smith.langchain.com/)
- [Agent Architecture Details](../architecture/agents.md)

---

*Date: 2026-01-08*
*Supersedes: None*
