# Family Scheduler - Architecture Overview

## Project Vision

A family scheduling and calendar application that demonstrates agent-based application development patterns. This project serves dual purposes:
1. **Learning Platform:** Hands-on experience with LangGraph, agent orchestration, and cloud deployment
2. **Practical Tool:** Real-world family scheduling with intelligent conflict detection and resource management

## Core Capabilities

### Natural Language Event Creation
Users can create events using natural language:
- "Schedule soccer practice Saturday at 2pm"
- "Book the car for dentist appointment Tuesday afternoon"
- "Add family dinner every Sunday at 6pm"

### Smart Scheduling
- Find optimal times based on participant availability
- Consider preferences and constraints
- Handle recurring events
- Respect time windows and gaps

### Conflict Detection & Resolution
- Detect time overlaps between events
- Identify resource over-capacity issues
- Validate against constraints (hard rules and soft preferences)
- Suggest intelligent resolutions

### Resource Management
- Manage shared resources (cars, kitchen, equipment)
- Support concurrent usage based on capacity
- Track reservations with or without events

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        User Interface                         │
│                   (Web UI / Mobile / API)                     │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                      │
│                                                               │
│  • HTTP endpoints                                             │
│  • Request validation                                         │
│  • Task creation (Phase 2: async via Celery)                 │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                   Orchestrator Agent (LangGraph)              │
│                                                               │
│  • Central coordinator for all agent workflows                │
│  • Routes requests to specialized agents                      │
│  • Manages conversation state                                 │
│  • Makes final decisions                                      │
└───────────────────────────────┬──────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│   NL Parser      │  │  Scheduling  │  │   Resource   │
│     Agent        │  │    Agent     │  │   Manager    │
└──────────────────┘  └──────────────┘  └──────────────┘
                ▼               ▼               ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│   Conflict       │  │  Resolution  │  │    Query     │
│   Detection      │  │    Agent     │  │    Agent     │
└──────────────────┘  └──────────────┘  └──────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                     Data Layer (PostgreSQL)                   │
│                                                               │
│  • Events & Calendars                                         │
│  • Resources & Reservations                                   │
│  • Family Members & Preferences                               │
│  • Conflicts & Constraints                                    │
└──────────────────────────────────────────────────────────────┘
```

## Key Design Principles

### 1. Hub-and-Spoke Agent Pattern
All agent communication flows through the orchestrator. This provides:
- Clear observability of all decisions
- Predictable workflow execution
- Easy debugging and troubleshooting
- Simple mental model for learning

### 2. Proposal Flow with Validation
Events are not immediately confirmed. Instead:
1. Parse user intent → Create proposed event
2. Validate through multiple agents (scheduling, resources, conflicts)
3. Auto-confirm if no issues, or present conflicts to user
4. User approves → Confirm event

This ensures data quality and gives users control.

### 3. Hybrid Agent Outputs
Agents return both structured data (for programmatic processing) and natural language explanations (for human understanding). This supports:
- Reliable orchestrator logic
- Transparent user communication
- Effective debugging

### 4. Observable State Management
LangGraph state is structured to make agent contributions visible:
- Each agent has dedicated output namespace
- Audit log tracks workflow progression
- State inspectable at any point

### 5. Phased Deployment Strategy
- **Phase 1 (Local):** Learn agent patterns without infrastructure complexity
- **Phase 2 (Cloud):** Learn scaling, containers, and task queues

## Technology Stack

### Phase 1 (Local Development)
- **Language:** Python 3.11+
- **Agent Framework:** LangGraph
- **API Framework:** FastAPI
- **Database:** SQLite
- **ORM:** SQLAlchemy
- **LLM:** OpenAI or Anthropic API

### Phase 2 (Cloud Deployment)
- **Platform:** Google Cloud Platform (GCP)
- **API Hosting:** Cloud Run (serverless containers)
- **Database:** Cloud SQL (PostgreSQL)
- **Task Queue:** Memorystore (Redis) + Celery
- **Agent Workers:** Cloud Run (auto-scaling)
- **State Storage:** Cloud Storage (LangGraph checkpoints)

## Learning Objectives

### Agent Development
- LangGraph state management
- Multi-agent orchestration
- Prompt engineering for specialized agents
- Error handling and recovery

### Infrastructure & Scaling
- Containerization (Docker)
- Task queue patterns (Celery)
- Horizontal scaling of agent workers
- Cloud deployment (GCP)
- Monitoring and observability

### Software Engineering
- API design with FastAPI
- Database modeling with SQLAlchemy
- Testing strategies for agent systems
- Git workflow and documentation

## Project Structure

```
family-scheduler/
├── docs/
│   ├── architecture/          # Architecture documentation
│   │   ├── overview.md        # This file
│   │   ├── agents.md          # Agent architecture details
│   │   ├── infrastructure.md  # Deployment and scaling
│   │   └── data-model.md      # Database schema
│   └── decisions/             # Architecture Decision Records
├── src/
│   ├── api/                   # FastAPI application
│   ├── agents/                # LangGraph agents
│   ├── models/                # SQLAlchemy models
│   ├── services/              # Business logic
│   └── utils/                 # Utilities
├── tests/                     # Test suite
├── requirements.txt           # Python dependencies
└── README.md                  # Project introduction
```

## Next Steps

1. **Phase 1 Setup:**
   - Set up Python environment
   - Implement SQLAlchemy models
   - Create basic FastAPI endpoints
   - Build orchestrator and first agents

2. **Local Development:**
   - Test agent workflows
   - Refine prompts and state management
   - Build simple UI for testing

3. **Cloud Deployment:**
   - Containerize application
   - Set up GCP infrastructure
   - Implement task queue
   - Deploy and scale

## References

- [Agent Architecture Details](./agents.md)
- [Infrastructure & Deployment](./infrastructure.md)
- [Data Model](./data-model.md)
- [Architecture Decision Records](../decisions/)

---

*Last Updated: 2026-01-08*
