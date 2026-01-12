"""
Alembic environment configuration for Family Scheduler.

This module configures Alembic to work with our SQLAlchemy models and database.
"""

import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import application config to get database URL
from src.config import get_settings

# Import Base for autogenerate support
from src.models.base import Base

# Import all models so Alembic can detect them for autogenerate
# This is critical - if a model isn't imported here, Alembic won't detect it
from src.models.family import FamilyMember, Calendar  # noqa: F401
from src.models.events import Event, EventParticipant  # noqa: F401
from src.models.resources import Resource, ResourceReservation  # noqa: F401
from src.models.constraints import Constraint  # noqa: F401
from src.models.conflicts import Conflict  # noqa: F401

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Get database URL from application settings (overrides alembic.ini)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we don't
    even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection with
    the context.
    """
    # Create engine from configuration
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections for migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE support
            compare_type=True,  # Detect column type changes
            compare_server_default=True,  # Detect server default changes
        )

        with context.begin_transaction():
            context.run_migrations()


# Determine which mode to run in
if context.is_offline_mode():
    logger.info("Running migrations offline")
    run_migrations_offline()
else:
    logger.info("Running migrations online")
    run_migrations_online()
