# ADR-010: Python Environment & Package Management

## Status
Implemented

**Implementation Status**: Implemented
**Implementation Date**: 2026-01-08

## Context

The Family Scheduler project has completed high-level architectural decisions (ADRs 1-9) covering agent framework, architecture patterns, and data models. However, before any code can be written, we need to establish the foundational development environment setup.

Key questions that must be answered:
- **Python Version**: Which version of Python should we use?
- **Package Management**: How do we manage dependencies and virtual environments?
- **Environment Configuration**: How do we handle configuration and secrets?
- **Project Structure**: What is the standard directory layout?
- **Development Workflow**: How do developers set up and run the project?

These decisions block all development activity. Without a defined package manager, we cannot install LangGraph, FastAPI, or any other dependencies. Without environment configuration standards, we cannot securely handle LLM API keys. Without a project structure, we cannot organize code consistently.

Since this is a learning project that will evolve through phases (local → cloud), we need an approach that:
- Supports learning modern Python best practices
- Enables reproducible builds across environments
- Simplifies dependency management
- Handles both development and production configurations
- Facilitates the eventual Phase 1 → Phase 2 migration

## Decision

We will use the following development environment setup:

### Python Version: 3.11

Use **Python 3.11.x** as the base version for the project.

**Rationale:**
- Already specified in architecture documentation
- Stable and mature (released October 2022)
- Excellent async/await support needed for FastAPI
- Fully supported by LangGraph, LangChain, and all major dependencies
- Performance improvements over 3.10 (up to 25% faster)
- More stable than 3.12 for production workloads (as of 2026-01)

### Package Management: Poetry

Use **Poetry** for dependency management and packaging.

**Rationale:**
- **Modern tooling**: Industry standard for Python projects in 2024-2026
- **Lockfile support**: `poetry.lock` ensures reproducible builds
- **Virtual environment management**: Automatically creates and manages venvs
- **Dependency resolution**: Smart resolver prevents dependency conflicts
- **Dev dependencies**: Clear separation of development vs production dependencies
- **PEP 517/518 compliant**: Uses modern `pyproject.toml` standard
- **Learning value**: Understanding Poetry is valuable for modern Python development

### Environment Configuration: `.env` Files

Use `.env` files with `python-dotenv` for environment variable management.

**Environment Variables Structure:**
```bash
# Python & Application
PYTHON_ENV=development              # development | production
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR

# Database
DATABASE_URL=sqlite:///./data/family_scheduler.db

# LLM Provider (to be decided in ADR-011)
LLM_PROVIDER=anthropic              # openai | anthropic
ANTHROPIC_API_KEY=                  # sk-ant-...
OPENAI_API_KEY=                     # sk-...

# LangSmith (optional observability)
LANGSMITH_API_KEY=                  # Optional: for agent tracing
LANGSMITH_PROJECT=family-scheduler-dev

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true                     # Auto-reload in dev mode
```

### Project Directory Structure

```
family_scheduler/
├── pyproject.toml          # Poetry configuration & dependencies
├── poetry.lock            # Locked dependency versions
├── .env                   # Local environment variables (gitignored)
├── .env.example          # Template for environment setup
├── .gitignore            # Git ignore rules
├── README.md             # Project documentation
├── docs/                 # Architecture documentation
│   ├── architecture/
│   └── decisions/
├── src/                  # Source code
│   ├── __init__.py
│   ├── api/             # FastAPI application
│   │   ├── __init__.py
│   │   └── main.py
│   ├── agents/          # LangGraph agents
│   │   ├── __init__.py
│   │   └── orchestrator.py
│   ├── models/          # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── base.py
│   ├── services/        # Business logic
│   │   └── __init__.py
│   ├── utils/           # Utilities
│   │   └── __init__.py
│   └── config.py        # Environment configuration loading
├── tests/               # Test suite
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/                # SQLite database location
│   └── .gitkeep
├── alembic/            # Database migrations
│   ├── versions/
│   └── env.py
└── scripts/            # Utility scripts
    └── setup_dev.sh
```

### Configuration Management

Use **Pydantic Settings** (`pydantic-settings`) for type-safe configuration loading:

```python
# src/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Python & App
    python_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./data/family_scheduler.db"

    # LLM Provider
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "family-scheduler-dev"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

## Consequences

### Positive

1. **Reproducible Builds**: `poetry.lock` ensures identical dependency versions across all environments
2. **Easy Setup**: New developers can set up with `poetry install` and copying `.env.example`
3. **Modern Standards**: Using current Python packaging best practices (PEP 517/518)
4. **Type Safety**: Pydantic Settings provides validation for configuration
5. **Clear Separation**: Dev vs prod dependencies clearly separated in `pyproject.toml`
6. **Learning Value**: Poetry is widely used; learning it benefits future projects
7. **Phase 2 Ready**: Setup supports containerization (Poetry works well in Docker)
8. **IDE Support**: Modern IDEs recognize `pyproject.toml` and integrate well with Poetry

### Negative

1. **Learning Curve**: Team must learn Poetry commands (`poetry add`, `poetry run`, etc.)
2. **Tool Dependency**: Another tool in the stack (Poetry must be installed separately)
3. **Slower Installs**: Poetry dependency resolution is slower than pip (marginal impact)
4. **Lock File Conflicts**: `poetry.lock` can cause merge conflicts in team environments
5. **Migration Effort**: If switching away from Poetry later, requires effort to convert

### Mitigation Strategies

- Document common Poetry commands in README for quick reference
- Provide `scripts/setup_dev.sh` for one-command setup
- Use `poetry export` to generate `requirements.txt` if needed for CI/Docker
- Include clear examples of `.env.example` to minimize configuration errors
- Add pre-commit hooks to ensure `.env` is never committed

## Alternatives Considered

### pip + requirements.txt

**Approach**: Traditional `requirements.txt` with venv for virtual environments

**Pros**:
- Most familiar to Python developers
- Simple and straightforward
- Minimal tooling required
- Fast install times

**Cons**:
- No lockfile (unless using `pip freeze`, which is brittle)
- Manual virtual environment management
- No clear dev vs prod dependency separation
- Dependency resolution conflicts common
- No modern packaging standards support

**Why not chosen**: Lacks reproducibility guarantees; managing dev vs prod dependencies is cumbersome; Poetry's benefits outweigh the learning curve for a project that will evolve to cloud deployment.

### Pipenv

**Approach**: Alternative dependency manager with Pipfile/Pipfile.lock

**Pros**:
- Lockfile support
- Virtual environment management
- Separate dev dependencies

**Cons**:
- Slower than Poetry
- Less actively maintained (development slowed after 2020)
- Larger community migrated to Poetry
- Some dependency resolution issues

**Why not chosen**: Poetry is more actively maintained, faster, and has better tooling support. Industry momentum favors Poetry for new projects.

### Conda/Mamba

**Approach**: Conda-based environment and package management

**Pros**:
- Great for data science projects
- Handles non-Python dependencies (C libraries, system packages)
- Mature ecosystem

**Cons**:
- Heavier than Poetry (large environment sizes)
- Slower environment creation
- Primarily designed for data science, not web services
- Less integration with modern Python packaging standards

**Why not chosen**: Overkill for this project; we don't need system-level dependency management. Poetry is lighter weight and more appropriate for a web service application.

### Python 3.12

**Approach**: Use newer Python 3.12 instead of 3.11

**Pros**:
- Latest features
- Improved error messages
- Performance improvements

**Cons**:
- Newer, less battle-tested
- Some libraries may have compatibility issues
- Less stable for production (as of 2026-01)

**Why not chosen**: 3.11 is stable and well-supported. The marginal benefits of 3.12 don't justify the potential compatibility risks for a learning project.

## Implementation Notes

### Initial Setup Commands

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Create project structure
cd family_scheduler
poetry init --python "^3.11"

# Add core dependencies
poetry add fastapi uvicorn[standard] sqlalchemy alembic
poetry add langchain langgraph langchain-anthropic langchain-openai
poetry add pydantic pydantic-settings python-dotenv
poetry add python-dateutil  # For RRULE handling

# Add development dependencies
poetry add --group dev pytest pytest-asyncio pytest-cov
poetry add --group dev black isort mypy ruff
poetry add --group dev pre-commit

# Install all dependencies
poetry install

# Set up environment file
cp .env.example .env
# Edit .env with your API keys

# Activate virtual environment (optional, poetry run handles this)
poetry shell
```

### `.gitignore` Additions

```gitignore
# Environment
.env
.env.local

# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# Virtual environments
.venv/
venv/
env/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Data
data/*.db
data/*.sqlite
data/*.sqlite3

# Poetry
poetry.lock  # Decision: commit this for reproducibility

# Alembic
alembic.ini  # If contains sensitive data
```

### Initial `pyproject.toml` Template

```toml
[tool.poetry]
name = "family-scheduler"
version = "0.1.0"
description = "Agent-based family scheduling application"
authors = ["Your Name <you@example.com>"]
readme = "README.md"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
sqlalchemy = "^2.0.25"
alembic = "^1.13.1"
langchain = "^0.1.0"
langgraph = "^0.0.20"
langchain-anthropic = "^0.1.0"
langchain-openai = "^0.0.5"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
python-dotenv = "^1.0.0"
python-dateutil = "^2.8.2"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.4"
pytest-asyncio = "^0.23.3"
pytest-cov = "^4.1.0"
black = "^24.1.0"
isort = "^5.13.2"
mypy = "^1.8.0"
ruff = "^0.1.14"
pre-commit = "^3.6.0"

[tool.poetry.scripts]
api = "src.api.main:main"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false

[tool.ruff]
line-length = 100
target-version = "py311"
```

### Development Workflow

```bash
# Daily development
poetry run uvicorn src.api.main:app --reload

# Run tests
poetry run pytest

# Run linters
poetry run black src/ tests/
poetry run isort src/ tests/
poetry run ruff check src/ tests/

# Add new dependency
poetry add <package-name>

# Add new dev dependency
poetry add --group dev <package-name>

# Update dependencies
poetry update
```

## References

- [Poetry Documentation](https://python-poetry.org/docs/)
- [PEP 517 - Build System](https://peps.python.org/pep-0517/)
- [PEP 518 - pyproject.toml](https://peps.python.org/pep-0518/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Architecture Overview](../architecture/overview.md)
- [ADR-006: Phased Infrastructure Deployment](./adr-006-phased-infrastructure-deployment.md)

## Implementation

**Implemented**: 2026-01-08

### What Was Created

1. **Poetry Configuration** (`pyproject.toml`)
   - Configured for Python 3.11+
   - Added all core dependencies: langchain, langgraph, fastapi, sqlalchemy, alembic
   - Added dev dependencies: pytest, black, isort, mypy, ruff, pre-commit
   - Configured linting tools (black, isort, ruff, mypy)
   - Created `api` script entry point

2. **Environment Configuration** (`.env.example`)
   - Complete environment variable template with all required settings
   - Sections for: Python/App, Database, LLM Provider, LangSmith, API, Security
   - Includes helpful comments and links to get API keys

3. **Configuration Management** (`src/config.py`)
   - Type-safe configuration using Pydantic Settings
   - Environment variable validation with proper types
   - Helper methods: `is_development`, `is_production`, `get_llm_api_key()`
   - Cached settings with `@lru_cache()` for performance

4. **Project Directory Structure**
   - Created: `src/` (api, agents, models, services, utils)
   - Created: `tests/` (unit, integration, fixtures)
   - Created: `data/` (for SQLite database)
   - Created: `alembic/versions/` (for migrations)
   - Created: `scripts/` (for utility scripts)
   - All Python directories include `__init__.py`

5. **Git Configuration** (`.gitignore`)
   - Updated to include Poetry-specific entries
   - Configured to track `poetry.lock` for reproducibility
   - Updated data/ ignores to keep `.gitkeep` while ignoring database files

6. **Documentation** (`README.md`)
   - Updated with Poetry installation instructions
   - Added quick start commands
   - Updated project structure diagram
   - Updated technology stack to mention Poetry
   - Updated Phase 1 status to show ADR-010 implemented

### Deviations from Plan

**None** - Implementation followed the ADR exactly as planned.

All decisions were implemented as specified:
- Poetry for package management ✅
- Python 3.11 as base version ✅
- .env files with Pydantic Settings ✅
- Specified directory structure ✅

### Lessons Learned

1. **Pydantic Settings**: The type-safe configuration with Pydantic Settings works excellently for catching configuration errors early.

2. **Poetry Setup**: Having `pyproject.toml` in place from the start provides clear dependency documentation and makes onboarding straightforward.

3. **Environment Template**: The detailed `.env.example` with comments and links is crucial for helping developers get started quickly.

4. **Directory Structure**: Creating all directories with `__init__.py` files upfront prevents import errors during development.

### Next Steps

1. **Install Dependencies**: Run `poetry install` to create virtual environment and install all packages
2. **Configure Environment**: Copy `.env.example` to `.env` and add API keys
3. **Test Setup**: Verify imports work: `poetry run python -c "import langchain; print('Success')"`
4. **Next ADR**: Document ADR-011 (LLM Provider Selection) to choose between OpenAI and Anthropic

### Verification Commands

```bash
# Verify Poetry project structure
poetry check

# Install dependencies
poetry install

# Verify configuration loads correctly
poetry run python -c "from src.config import get_settings; print(get_settings())"

# Verify all imports work
poetry run python -c "import fastapi, langchain, langgraph, sqlalchemy"
```

### Related Files

- `/pyproject.toml` - Poetry configuration
- `/.env.example` - Environment variable template
- `/src/config.py` - Configuration management
- `/README.md` - Updated setup instructions
- `/.gitignore` - Updated ignore rules

---

*Date: 2026-01-08*
*Supersedes: None*
