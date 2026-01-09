# Family Scheduler

An intelligent family scheduling and calendar application built with agent-based architecture using LangGraph.

## Overview

Family Scheduler is a learning project designed to explore agent-based application development while creating a practical tool for family coordination. The system uses multiple specialized AI agents to handle natural language event creation, smart scheduling, conflict detection, and resource management.

## Key Features

- **Natural Language Event Creation**: "Schedule soccer practice Saturday at 2pm"
- **Smart Scheduling**: Find optimal times based on availability and preferences
- **Conflict Detection**: Identify scheduling conflicts and constraint violations
- **Resource Management**: Manage shared resources (cars, kitchen, etc.) with capacity
- **Intelligent Resolution**: AI-powered conflict resolution suggestions
- **Recurring Events**: Support for repeating events with flexible exceptions

## Architecture

The system uses a **hub-and-spoke agent architecture** where a central orchestrator coordinates specialized agents:

- **NL Parser Agent**: Interprets natural language input
- **Scheduling Agent**: Finds optimal time slots
- **Resource Manager Agent**: Checks resource availability
- **Conflict Detection Agent**: Identifies conflicts
- **Resolution Agent**: Suggests solutions
- **Query Agent**: Answers scheduling questions

[View detailed architecture documentation →](docs/architecture/overview.md)

## Technology Stack

### Phase 1 (Local Development - Current)
- **Language**: Python 3.11+
- **Package Manager**: Poetry
- **Agent Framework**: LangGraph
- **API**: FastAPI
- **Database**: SQLite
- **ORM**: SQLAlchemy

### Phase 2 (Cloud Deployment - Planned)
- **Platform**: Google Cloud Platform (GCP)
- **Compute**: Cloud Run (serverless containers)
- **Database**: Cloud SQL (PostgreSQL)
- **Task Queue**: Redis + Celery
- **Scaling**: Auto-scaling agent workers

## Project Structure

```
family-scheduler/
├── docs/
│   ├── architecture/           # Architecture documentation
│   │   ├── overview.md         # System overview
│   │   ├── agents.md           # Agent architecture details
│   │   ├── infrastructure.md   # Deployment and scaling
│   │   └── data-model.md       # Database schema
│   └── decisions/              # Architecture Decision Records (ADRs)
├── src/
│   ├── api/                    # FastAPI application
│   ├── agents/                 # LangGraph agents
│   ├── models/                 # SQLAlchemy models
│   ├── services/               # Business logic
│   ├── utils/                  # Utilities
│   └── config.py               # Configuration management
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fixtures/               # Test fixtures
├── data/                       # SQLite database location
├── alembic/                    # Database migrations
├── scripts/                    # Utility scripts
├── pyproject.toml              # Poetry configuration & dependencies
├── poetry.lock                 # Locked dependency versions
├── .env.example                # Environment variable template
└── README.md                   # This file
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [Poetry](https://python-poetry.org/) (Python dependency manager)
- OpenAI or Anthropic API key (for LLM agents)

### Installation

#### 1. Install Poetry (if not already installed)

```bash
# macOS/Linux/WSL
curl -sSL https://install.python-poetry.org | python3 -

# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

#### 2. Get Anthropic API Key

The project uses Anthropic's Claude API for all AI agents.

1. Sign up at [Anthropic Console](https://console.anthropic.com/)
2. Navigate to **API Keys** section
3. Create a new key (name it "Family Scheduler Development")
4. Copy the key (starts with `sk-ant-api03-...`)

**Cost Estimate**: Development typically costs $20-50/month with Claude 3.5 Sonnet.

#### 3. Set up the project

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/family-scheduler.git
cd family-scheduler

# Install dependencies (Poetry will create virtual environment automatically)
poetry install

# Set up environment variables
cp .env.example .env
# Edit .env and add your Anthropic API key:
# ANTHROPIC_API_KEY=sk-ant-api03-...

# Initialize database
poetry run alembic upgrade head

# Run development server
poetry run uvicorn src.api.main:app --reload
```

### Quick Start Commands

```bash
# Activate Poetry shell (optional, makes commands shorter)
poetry shell

# Run API server
poetry run uvicorn src.api.main:app --reload

# Run tests
poetry run pytest

# Run linters
poetry run black src/ tests/
poetry run ruff check src/ tests/

# Add new dependency
poetry add package-name

# Add dev dependency
poetry add --group dev package-name
```

### Usage

Once the server is running, access:
- API documentation: http://localhost:8000/docs
- Interactive API: http://localhost:8000/redoc

Example API call:
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"message": "Schedule soccer practice Saturday at 2pm"}'
```

## Learning Goals

This project is designed to teach:

1. **Agent-Based Application Development**
   - LangGraph state management
   - Multi-agent orchestration
   - Prompt engineering for specialized agents

2. **Infrastructure & Scaling**
   - Containerization with Docker
   - Task queue patterns (Celery)
   - Horizontal scaling of agent workers
   - Cloud deployment (GCP)

3. **Software Engineering Best Practices**
   - API design with FastAPI
   - Database modeling with SQLAlchemy
   - Testing strategies for agent systems
   - Documentation and decision tracking

## Development Phases

### Phase 1: Local Development (Current)
- ✅ Architecture design complete (ADRs 1-9)
- ✅ Development environment setup (ADR-010)
- ✅ LLM provider configuration (ADR-011)
- 🔄 Implement core data models
- 🔄 Build FastAPI endpoints
- 🔄 Create orchestrator and agents
- 🔄 Local testing and refinement

### Phase 2: Cloud Deployment (Planned)
- Containerize application
- Set up GCP infrastructure
- Implement Celery task queue
- Deploy and configure auto-scaling
- Monitor and optimize

### Phase 3: Advanced Features (Future)
- Mobile app integration
- Advanced conflict resolution strategies
- Analytics and insights
- Multi-region deployment

## Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Agent Architecture](docs/architecture/agents.md)
- [Infrastructure & Deployment](docs/architecture/infrastructure.md)
- [Data Model](docs/architecture/data-model.md)
- [Architecture Decision Records](docs/decisions/README.md)

## Contributing

This is a personal learning project, but feedback and suggestions are welcome! Please open an issue to discuss potential changes.

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built with:
- [LangChain](https://python.langchain.com/) - LLM application framework
- [LangGraph](https://python.langchain.com/docs/langgraph) - Agent orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - SQL toolkit and ORM

---

**Project Status**: In Development (Phase 1)

**Last Updated**: 2026-01-08
