"""
Event and EventParticipant models.

Entities:
- Event: Represents a scheduled event or activity
- EventParticipant: Many-to-many association between Events and FamilyMembers
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel, get_json_type

# Avoid circular imports for type hints
if TYPE_CHECKING:
    from src.models.family import Calendar, FamilyMember
    from src.models.resources import ResourceReservation
    from src.models.conflicts import Conflict


class Event(BaseModel):
    """
    Represents a scheduled event or activity.

    Events can be:
    - One-time or recurring (via RRULE)
    - Proposed, confirmed, or cancelled
    - Associated with a calendar, participants, and resources
    - Part of a recurrence series (parent/child relationship)

    Key features:
    - Status workflow (proposed → confirmed/cancelled)
    - Priority and flexibility for conflict resolution
    - RRULE-based recurrence with exception handling
    - Metadata for extensibility
    """

    __tablename__ = "events"

    # Basic event information
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendars.id"),
        nullable=False,
        doc="Calendar this event belongs to"
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Event title/summary"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed event description"
    )

    # Timing
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Event start time (UTC)"
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Event end time (UTC)"
    )

    all_day: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether this is an all-day event"
    )

    # Location
    location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        doc="Event location (address, room name, etc.)"
    )

    # Status and workflow
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="proposed",
        doc="Event status: 'proposed', 'confirmed', 'cancelled'"
    )

    priority: Mapped[str] = mapped_column(
        String(50),
        default="medium",
        nullable=False,
        doc="Priority: 'low', 'medium', 'high', 'critical'"
    )

    flexibility: Mapped[str] = mapped_column(
        String(50),
        default="fixed",
        nullable=False,
        doc="Scheduling flexibility: 'fixed', 'preferred', 'flexible'"
    )

    # Recurrence fields (hybrid model per ADR-007)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="iCalendar RRULE format (e.g., 'FREQ=WEEKLY;BYDAY=MO,WE,FR')"
    )

    recurrence_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Recurrence instance identifier (YYYYMMDDTHHMMSS format)"
    )

    original_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("events.id"),
        nullable=True,
        doc="Parent event ID for recurrence exceptions"
    )

    # Status timestamps for audit trail
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when event was proposed"
    )

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when event was confirmed"
    )

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when event was cancelled"
    )

    # Creation tracking
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=False,
        doc="Family member who created this event"
    )

    # Flexible metadata storage (renamed from 'metadata' to avoid SQLAlchemy conflict)
    event_metadata: Mapped[dict] = mapped_column(
        get_json_type(),
        nullable=False,
        default=dict,
        doc="Additional event metadata (custom fields, integration data, etc.)"
    )

    # Relationships
    calendar: Mapped["Calendar"] = relationship(
        "Calendar",
        back_populates="events",
        doc="Calendar this event belongs to"
    )

    creator: Mapped["FamilyMember"] = relationship(
        "FamilyMember",
        foreign_keys=[created_by],
        doc="Family member who created this event"
    )

    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant",
        back_populates="event",
        cascade="all, delete-orphan",
        doc="Event participants (many-to-many via EventParticipant)"
    )

    resource_reservations: Mapped[list["ResourceReservation"]] = relationship(
        "ResourceReservation",
        back_populates="event",
        cascade="all, delete-orphan",
        doc="Resource reservations for this event"
    )

    # Recurrence relationships
    original_event: Mapped[Optional["Event"]] = relationship(
        "Event",
        remote_side="Event.id",
        foreign_keys=[original_event_id],
        doc="Parent event if this is a recurrence exception"
    )

    exception_events: Mapped[list["Event"]] = relationship(
        "Event",
        foreign_keys="Event.original_event_id",
        overlaps="original_event",
        doc="Exception events for this recurring event"
    )

    # Conflict relationships
    proposed_conflicts: Mapped[list["Conflict"]] = relationship(
        "Conflict",
        foreign_keys="Conflict.proposed_event_id",
        back_populates="proposed_event",
        doc="Conflicts where this event is proposed"
    )

    conflicting_with: Mapped[list["Conflict"]] = relationship(
        "Conflict",
        foreign_keys="Conflict.conflicting_event_id",
        back_populates="conflicting_event",
        doc="Conflicts where this event conflicts with another"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_event_calendar", "calendar_id"),
        Index("idx_event_start_time", "start_time"),
        Index("idx_event_end_time", "end_time"),
        Index("idx_event_status", "status"),
        Index("idx_event_created_by", "created_by"),
        Index("idx_event_original", "original_event_id"),
        Index("idx_event_deleted", "deleted_at"),
        # Composite index for time-range queries
        Index("idx_event_time_range", "calendar_id", "start_time", "end_time"),
        Index("idx_event_status_time", "status", "start_time", "end_time"),
    )

    def __repr__(self) -> str:
        """String representation showing title and time."""
        return f"<Event(title='{self.title}', start='{self.start_time}', status='{self.status}')>"


class EventParticipant(BaseModel):
    """
    Many-to-many association between Events and FamilyMembers.

    Represents a family member's participation in an event.
    Uses the association object pattern to store additional participation metadata.

    Fields:
    - required: Whether this participant is essential for the event
    - participation_status: Invitation response status (future)
    - response_time: When participant responded (future)
    """

    __tablename__ = "event_participants"

    # Relationships
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        doc="Event ID"
    )

    family_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=False,
        doc="Family member ID"
    )

    # Participation metadata
    required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether this participant is required for the event"
    )

    participation_status: Mapped[str] = mapped_column(
        String(50),
        default="accepted",
        nullable=False,
        doc="Status: 'invited', 'accepted', 'declined', 'tentative' (Phase 1: auto-accepted)"
    )

    response_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when participant responded to invitation"
    )

    # Relationships (note: EventParticipant does NOT have soft deletion)
    event: Mapped["Event"] = relationship(
        "Event",
        back_populates="participants",
        doc="Event this participation is for"
    )

    family_member: Mapped["FamilyMember"] = relationship(
        "FamilyMember",
        back_populates="participations",
        doc="Family member participating in event"
    )

    # Indexes and constraints
    __table_args__ = (
        # Unique constraint: one participation record per event-member pair
        UniqueConstraint("event_id", "family_member_id", name="uq_event_participant"),
        Index("idx_participant_event", "event_id"),
        Index("idx_participant_member", "family_member_id"),
        Index("idx_participant_required", "required"),
    )

    def __repr__(self) -> str:
        """String representation showing event and member IDs."""
        return f"<EventParticipant(event_id={self.event_id}, member_id={self.family_member_id}, required={self.required})>"
