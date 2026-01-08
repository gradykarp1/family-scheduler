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
│   └── decisions/              # Architecture Decision Records
├── src/
│   ├── api/                    # FastAPI application
│   ├── agents/                 # LangGraph agents
│   ├── models/                 # SQLAlchemy models
│   ├── services/               # Business logic
│   └── utils/                  # Utilities
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment tool (venv, virtualenv, or Poetry)
- OpenAI or Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/family-scheduler.git
cd family-scheduler

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your LLM API key

# Initialize database
alembic upgrade head

# Run development server
uvicorn src.api.main:app --reload
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
- ✅ Architecture design complete
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
