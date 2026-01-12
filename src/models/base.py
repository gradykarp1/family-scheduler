"""
Base model definitions for SQLAlchemy.

Provides:
- GUID TypeDecorator for UUID support across SQLite and PostgreSQL
- BaseModel declarative base with common fields
- Soft deletion mixin
- JSON/JSONB column factory function
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, JSON, TypeDecorator, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQL_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR

from src.config import get_settings


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type on PostgreSQL databases.
    Uses CHAR(32) on SQLite databases (stores hex representation).

    This allows the same model definitions to work across both databases.
    """

    impl = CHAR(32)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate type for the dialect."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        """
        Convert UUID to database-appropriate format.

        PostgreSQL: Store as UUID type (string representation)
        SQLite: Store as CHAR(32) (hex representation without dashes)
        """
        if value is None:
            return value

        if dialect.name == "postgresql":
            return str(value)
        else:
            # SQLite: store hex without dashes
            if isinstance(value, uuid.UUID):
                return value.hex
            else:
                # If string UUID, convert to hex
                return uuid.UUID(value).hex if value else None

    def process_result_value(self, value, dialect):
        """
        Convert database value back to UUID.

        Handles both PostgreSQL UUID strings and SQLite hex strings.
        """
        if value is None:
            return value

        if isinstance(value, uuid.UUID):
            return value

        # Convert string to UUID
        return uuid.UUID(value)


def get_json_type():
    """
    Get database-appropriate JSON column type.

    Returns:
        JSONB for PostgreSQL (with indexing support)
        JSON for SQLite (basic JSON support)
    """
    settings = get_settings()
    db_url = settings.database_url

    if "postgres" in db_url.lower():
        return JSONB
    return JSON


class Base(DeclarativeBase):
    """Declarative base for all models."""

    # Use this type annotation map for modern SQLAlchemy 2.0 style
    type_annotation_map = {
        uuid.UUID: GUID,
    }


class BaseModel(Base):
    """
    Base model with common fields for all entities.

    Provides:
    - id: UUID primary key
    - created_at: Timestamp of record creation (UTC)
    - updated_at: Timestamp of last update (UTC, auto-updates)
    - deleted_at: Timestamp of soft deletion (NULL if not deleted)

    All subclasses automatically inherit these fields.
    """

    __abstract__ = True

    # Primary key - UUID for distributed ID generation
    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier (UUID)"
    )

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp of record creation (UTC)"
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        doc="Timestamp of last update (UTC)"
    )

    # Soft deletion support
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Timestamp of soft deletion (NULL if not deleted)"
    )

    def to_dict(self) -> dict:
        """
        Convert model instance to dictionary.

        Returns:
            Dictionary with all column values (excludes relationships)
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def soft_delete(self) -> None:
        """
        Mark record as deleted by setting deleted_at timestamp.

        Does not remove the record from the database, preserving audit trail.
        """
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        """
        Check if record is soft-deleted.

        Returns:
            True if deleted_at is set, False otherwise
        """
        return self.deleted_at is not None

    def __repr__(self) -> str:
        """String representation showing class name and ID."""
        return f"<{self.__class__.__name__}(id={self.id})>"
