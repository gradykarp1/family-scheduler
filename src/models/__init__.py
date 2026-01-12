"""
SQLAlchemy models for Family Scheduler.

This module exports all database models for easy importing and
ensures Alembic can discover them for migrations.
"""

# Import base classes
from src.models.base import Base, BaseModel, GUID, get_json_type

# Import all models (must be imported for Alembic autogenerate)
from src.models.family import FamilyMember, Calendar
from src.models.events import Event, EventParticipant
from src.models.resources import Resource, ResourceReservation
from src.models.constraints import Constraint
from src.models.conflicts import Conflict

# Export all for easy importing
__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "GUID",
    "get_json_type",
    # Family models
    "FamilyMember",
    "Calendar",
    # Event models
    "Event",
    "EventParticipant",
    # Resource models
    "Resource",
    "ResourceReservation",
    # Constraint model
    "Constraint",
    # Conflict model
    "Conflict",
]
