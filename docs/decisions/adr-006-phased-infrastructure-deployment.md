# ADR-006: Phased Infrastructure Deployment

## Status
Accepted

## Context

The Family Scheduler project has dual objectives:
1. **Learning Platform**: Learn agent-based development, LangGraph, and cloud deployment
2. **Practical Tool**: Build a real family scheduling application

We need to decide on the deployment strategy and infrastructure approach. Key considerations:

- **Learning Objectives**: Want to learn both agent patterns and cloud infrastructure
- **Complexity Management**: Cloud deployment adds significant complexity
- **Development Speed**: Need fast iteration for agent development
- **Cost**: Cloud infrastructure has ongoing costs
- **Scaling Requirements**: Family scheduling doesn't need high scale initially
- **Time Investment**: Setting up infrastructure takes significant time

Several approaches are possible:
1. **Cloud-First**: Start with full cloud infrastructure (GCP, containers, databases)
2. **Local-Only**: Develop entirely locally, never deploy to cloud
3. **Phased Approach**: Start local, evolve to cloud when agent patterns are proven
4. **Hybrid**: Develop locally but with cloud-like architecture (Docker, etc.)

The challenge is balancing learning goals (want to learn cloud deployment) with pragmatism (don't want infrastructure to block agent development).

## Decision

We will use a **phased deployment strategy**:

### Phase 1: Local Development (Learn Agent Patterns)
**Focus**: LangGraph, agent orchestration, prompt engineering

**Architecture:**
- Python FastAPI application
- SQLite database (file-based)
- Agents run in-process (same process as API)
- Local development server (Uvicorn)
- No containers, no cloud services

**Goal**: Learn agent patterns without infrastructure complexity

**Duration**: Until agent workflows are working and tested

### Phase 2: Cloud Deployment (Learn Infrastructure & Scaling)
**Focus**: Containers, task queues, horizontal scaling, cloud services

**Architecture:**
- Google Cloud Platform (GCP)
- Cloud Run (serverless containers for API and workers)
- Cloud SQL (PostgreSQL)
- Memorystore (Redis for Celery task queue)
- Cloud Storage (LangGraph checkpoints)
- Horizontal agent scaling

**Goal**: Learn cloud deployment, containerization, and scaling patterns

**Trigger**: When Phase 1 agent workflows are stable and tested

### Phase 3: Advanced Scaling (Future)
**Focus**: Multi-region, advanced patterns (optional)

**Deferred** until core functionality proven valuable.

## Consequences

### Positive

1. **Separation of Concerns**: Learn agents first, infrastructure second
2. **Fast Initial Progress**: No infrastructure setup blocks agent development
3. **Lower Initial Cost**: Zero infrastructure costs during Phase 1
4. **Focused Learning**: Master one domain before adding complexity
5. **Validation**: Prove agent patterns work before investing in infrastructure
6. **Natural Migration Path**: SQLite → PostgreSQL is straightforward
7. **Clear Milestones**: Distinct phases provide clear achievement markers
8. **Risk Reduction**: Can stop after Phase 1 if agent patterns don't work
9. **Cost Control**: Only pay for cloud when actually needed

### Negative

1. **Architecture Shift**: Some code changes needed for Phase 1 → Phase 2 transition
2. **Delayed Cloud Learning**: Don't learn infrastructure until later
3. **SQLite Limitations**: No concurrent writes, limited scaling in Phase 1
4. **Testing Gap**: Phase 1 doesn't test production-like environment
5. **Potential Re-work**: Some Phase 1 patterns may not work in Phase 2
6. **Integration Testing**: Can't fully test agent scaling until Phase 2

### Mitigation Strategies

**Design for Migration:**
- Use SQLAlchemy ORM (works with both SQLite and PostgreSQL)
- Abstract database operations into service layer
- Design agents to be stateless (easy to scale horizontally)
- Use environment variables for configuration
- Keep business logic separate from infrastructure

**Minimize Re-work:**
- Write clean, testable code from the start
- Use async patterns where appropriate
- Design agent workflows assuming eventual asynchronous execution
- Document assumptions that will change in Phase 2

**Test Phase 2 Patterns:**
- Use Docker locally to validate containerization works
- Test with PostgreSQL in local container if desired
- Simulate task queue patterns even if not implemented

## Phase 1 Details

**Technology Stack:**
- Python 3.11+
- FastAPI + Uvicorn
- LangGraph + LangChain
- SQLite + SQLAlchemy
- OpenAI or Anthropic API

**Setup Time**: ~1 hour
**Monthly Cost**: $5-20 (LLM API only)

**Development Workflow:**
```bash
# One-time setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Daily development
uvicorn src.api.main:app --reload
# Edit code, test via http://localhost:8000/docs
```

**What You Learn:**
- LangGraph state management
- Agent orchestration patterns
- Prompt engineering
- FastAPI development
- Database modeling

## Phase 2 Details

**Technology Stack:**
- GCP Cloud Run (API + workers)
- Cloud SQL (PostgreSQL)
- Memorystore (Redis + Celery)
- Cloud Storage (checkpoints)
- Docker

**Setup Time**: ~2-3 days
**Monthly Cost**: $51-107 (estimated)

**What You Learn:**
- Docker containerization
- Cloud deployment (GCP)
- Task queue patterns (Celery)
- Horizontal scaling
- Monitoring and logging
- Infrastructure as code

**Migration Checklist:**
- [ ] Containerize application (Dockerfile)
- [ ] Migrate SQLite → PostgreSQL
- [ ] Implement Celery tasks for agent workflows
- [ ] Deploy to Cloud Run
- [ ] Set up task queue infrastructure
- [ ] Configure monitoring and alerting
- [ ] Test agent scaling under load

## Phase Transition Criteria

**Ready to move Phase 1 → Phase 2 when:**
1. Core agent workflows are implemented and tested
2. Event creation/modification works end-to-end
3. Conflict detection and resolution functional
4. Test suite has good coverage
5. Local performance is acceptable
6. Learning goals for agent patterns achieved
7. Ready to invest time in infrastructure

**Can stay in Phase 1 if:**
- Agent patterns need more refinement
- Not ready for infrastructure complexity
- Cost is a concern
- Single-user access is sufficient

## Alternatives Considered

### Cloud-First Approach
**Pros**: Learn everything at once, production-ready from start, no migration needed
**Cons**: High upfront complexity, slow initial progress, infrastructure blocks agent learning, costs from day one
**Why not chosen**: Learning two complex domains simultaneously is overwhelming; want to master agents first

### Local-Only (No Phase 2)
**Pros**: Simplest possible, zero infrastructure costs, no deployment complexity
**Cons**: Defeats learning goal of cloud deployment, no scaling, not accessible to family
**Why not chosen**: Misses important learning objectives around deployment and scaling

### Hybrid (Docker from Start)
**Pros**: Consistent environment, easier Phase 2 migration, teaches containers early
**Cons**: Adds complexity to Phase 1, slower development cycle, not necessary for learning agents
**Why not chosen**: Docker isn't needed for agent learning; adds overhead without benefit in Phase 1

### Serverless-First (Cloud Functions)
**Pros**: Minimal infrastructure, auto-scaling, low cost
**Cons**: Cold start latency, function timeout limits, stateful agent workflows challenging
**Why not chosen**: Serverless constraints complicate agent workflows; Cloud Run better fit

## Future Considerations (Phase 3+)

Potential enhancements if project scales:
- Multi-region deployment
- Kubernetes (GKE) for finer control
- Advanced caching strategies
- Real-time updates (WebSockets)
- Mobile applications
- Multi-family/organization support

These remain **deferred** until Phase 2 proves the value.

## References

- [Infrastructure & Deployment Documentation](../architecture/infrastructure.md)
- [Architecture Overview - Technology Stack](../architecture/overview.md#technology-stack)

---

*Date: 2026-01-08*
*Supersedes: None*
