"""
SQLAlchemy models for Family Scheduler.

This module exports database models for family configuration.
Events are stored in Google Calendar, not the local database.

Tables:
- family_members: Family member profiles and preferences
- calendars: Google Calendar references and configuration
- resources: Shared family resources (cars, rooms, etc.)
- constraints: Scheduling rules and preferences
"""

# Import base classes
from src.models.base import Base, BaseModel, GUID, get_json_type

# Import configuration models
from src.models.family import FamilyMember, Calendar
from src.models.resources import Resource
from src.models.constraints import Constraint

# Export all for easy importing
__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "GUID",
    "get_json_type",
    # Family configuration
    "FamilyMember",
    "Calendar",
    # Resource configuration
    "Resource",
    # Constraint configuration
    "Constraint",
]
