"""
Database configuration and session management.

Provides:
- Database engine creation with proper configuration
- SessionLocal factory for creating database sessions
- get_db() dependency for FastAPI request-scoped sessions
- Async session support for async endpoints
- Database initialization utilities
"""

import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Validate production configuration
if settings.is_production:
    settings.validate_production_config()

# Configure engine based on database type
if "sqlite" in settings.database_url.lower():
    # SQLite-specific configuration
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},  # Allow multiple threads (needed for FastAPI)
        poolclass=StaticPool,  # Use static pool for SQLite (single-file database)
        echo=settings.log_level == "DEBUG",  # Log SQL statements in debug mode
    )

    # Enable foreign key constraints for SQLite
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key constraints in SQLite."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # PostgreSQL-specific configuration
    engine = create_engine(
        settings.database_url,
        pool_size=5,  # Maximum number of connections in pool
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_pre_ping=True,  # Test connections before using them
        echo=settings.log_level == "DEBUG",
    )


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,  # Explicit commits required
    autoflush=False,  # Don't flush automatically before queries
    bind=engine,
)


# =============================================================================
# Async Engine and Session (for async endpoints)
# =============================================================================

def _get_async_database_url(sync_url: str) -> str:
    """Convert sync database URL to async URL."""
    if "sqlite" in sync_url.lower():
        # SQLite async uses aiosqlite
        return sync_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif "postgresql" in sync_url.lower():
        # PostgreSQL async uses asyncpg
        return sync_url.replace("postgresql://", "postgresql+asyncpg://")
    return sync_url


# Create async engine
async_database_url = _get_async_database_url(settings.database_url)

if "sqlite" in settings.database_url.lower():
    async_engine = create_async_engine(
        async_database_url,
        echo=settings.log_level == "DEBUG",
    )
else:
    async_engine = create_async_engine(
        async_database_url,
        pool_size=5,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=settings.log_level == "DEBUG",
    )

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for request-scoped database sessions.

    Yields a database session that is automatically closed after the request.
    Automatically rolls back on exception.

    Usage in FastAPI:
        @app.get("/events")
        def get_events(db: Session = Depends(get_db)):
            events = db.query(Event).all()
            return events

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit on successful request
    except Exception:
        db.rollback()  # Rollback on error
        raise
    finally:
        db.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions.

    Yields an async database session that is automatically closed after the request.
    Automatically rolls back on exception.

    Usage in FastAPI:
        @app.get("/events")
        async def get_events(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(Event))
            return result.scalars().all()

    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions outside FastAPI.

    Usage for scripts, tests, or background tasks:
        async with get_async_db_context() as session:
            result = await session.execute(select(Event))
            events = result.scalars().all()

    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside FastAPI.

    Usage for scripts, tests, or background tasks:
        with get_db_context() as db:
            event = db.query(Event).first()
            event.title = "Updated"
            # Automatic commit on context exit

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.

    This is useful for development and testing. In production, use Alembic migrations.

    Note: This does not run migrations - use `alembic upgrade head` for that.
    """
    from src.models.base import Base

    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_all_tables() -> None:
    """
    Drop all tables from the database.

    WARNING: This will delete all data. Use with caution.
    Primarily for testing and development.
    """
    from src.models.base import Base

    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All database tables dropped")


def get_session() -> Session:
    """
    Get a new database session.

    Use this for non-FastAPI contexts where you want manual session management.

    Returns:
        Session: New database session (must be closed manually)

    Example:
        session = get_session()
        try:
            event = session.query(Event).first()
            session.commit()
        finally:
            session.close()
    """
    return SessionLocal()


def check_connection() -> bool:
    """
    Test database connection.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
