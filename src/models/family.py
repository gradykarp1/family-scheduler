"""
Family and Calendar models.

Entities:
- FamilyMember: Represents a person in the family who participates in events
- Calendar: Configuration for a Google Calendar (personal, family, shared)

Note: Events are stored in Google Calendar, not the local database.
This module stores family configuration and calendar references only.
"""

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel, get_json_type

# Avoid circular imports for type hints
if TYPE_CHECKING:
    from src.models.constraints import Constraint


class FamilyMember(BaseModel):
    """
    Represents a person in the family who participates in events.

    Each family member has:
    - Personal information (name, email, role)
    - Preferences for scheduling (stored as JSON)
    - A default calendar for their events
    - Relationships to constraints and calendars
    """

    __tablename__ = "family_members"

    # Personal information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Full name of the family member"
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        doc="Email address for notifications and Google Calendar sync"
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Role in family: 'parent', 'child', 'other'"
    )

    # Preferences stored as JSON for flexibility
    preferences: Mapped[dict] = mapped_column(
        get_json_type(),
        nullable=False,
        default=dict,
        doc="Scheduling preferences (preferred times, notification settings, etc.)"
    )

    # Default calendar relationship
    default_calendar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("calendars.id"),
        nullable=True,
        doc="Default calendar for this family member's events"
    )

    # Relationships
    default_calendar: Mapped[Optional["Calendar"]] = relationship(
        "Calendar",
        foreign_keys=[default_calendar_id],
        back_populates="default_for_members",
        doc="Default calendar for this family member"
    )

    owned_calendars: Mapped[list["Calendar"]] = relationship(
        "Calendar",
        foreign_keys="Calendar.owner_id",
        back_populates="owner",
        doc="Calendars owned by this family member"
    )

    constraints: Mapped[list["Constraint"]] = relationship(
        "Constraint",
        back_populates="family_member",
        doc="Scheduling constraints for this family member"
    )

    # Indexes
    __table_args__ = (
        Index("idx_family_member_email", "email"),
        Index("idx_family_member_role", "role"),
        Index("idx_family_member_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        """String representation showing name and role."""
        return f"<FamilyMember(name='{self.name}', role='{self.role}')>"


class Calendar(BaseModel):
    """
    Configuration for a Google Calendar.

    Types of calendars:
    - Personal: Belongs to a specific family member
    - Family: Shared calendar for all family events
    - Shared: Shared with specific family members

    This model stores the reference to the Google Calendar ID,
    not the events themselves (those are in Google Calendar).
    """

    __tablename__ = "calendars"

    # Calendar identification
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Calendar name (e.g., 'Mom's Calendar', 'Family Calendar')"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Optional description of calendar purpose"
    )

    # Calendar type
    calendar_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Calendar type: 'personal', 'family', 'shared'"
    )

    # Google Calendar ID (the actual calendar in Google)
    google_calendar_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Google Calendar ID for syncing events"
    )

    # Visual appearance
    color: Mapped[Optional[str]] = mapped_column(
        String(7),
        nullable=True,
        default="#3B82F6",
        doc="Hex color code for calendar display (e.g., '#3B82F6')"
    )

    # Ownership
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=True,
        doc="Owner of calendar (NULL for family calendars)"
    )

    # Visibility
    visibility: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="family",
        doc="Visibility: 'private', 'family', 'public'"
    )

    # Relationships
    owner: Mapped[Optional["FamilyMember"]] = relationship(
        "FamilyMember",
        foreign_keys=[owner_id],
        back_populates="owned_calendars",
        doc="Owner of this calendar"
    )

    default_for_members: Mapped[list["FamilyMember"]] = relationship(
        "FamilyMember",
        foreign_keys="FamilyMember.default_calendar_id",
        back_populates="default_calendar",
        doc="Family members who use this as their default calendar"
    )

    # Indexes
    __table_args__ = (
        Index("idx_calendar_type", "calendar_type"),
        Index("idx_calendar_owner", "owner_id"),
        Index("idx_calendar_google_id", "google_calendar_id"),
        Index("idx_calendar_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        """String representation showing name and type."""
        return f"<Calendar(name='{self.name}', type='{self.calendar_type}')>"
