"""
Resource and ResourceReservation models.

Entities:
- Resource: Represents shared family resources (vehicles, rooms, equipment)
- ResourceReservation: Tracks resource bookings linked to events
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel, get_json_type

# Avoid circular imports for type hints
if TYPE_CHECKING:
    from src.models.events import Event
    from src.models.family import FamilyMember


class Resource(BaseModel):
    """
    Represents a shared family resource that can be reserved.

    Resources include:
    - Vehicles (cars, bikes)
    - Rooms (kitchen, garage, home office)
    - Equipment (laptop, tools, sports gear)

    Key features:
    - Capacity model: supports concurrent usage (capacity > 1)
    - Flexible attributes stored as JSON
    - Active/inactive status for lifecycle management
    """

    __tablename__ = "resources"

    # Basic information
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Resource name (e.g., 'Family Car', 'Kitchen', 'Shared Laptop')"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of the resource"
    )

    # Resource type
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Resource type: 'vehicle', 'room', 'equipment', 'other'"
    )

    # Capacity model (ADR-008)
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Maximum concurrent usage (1 = exclusive, >1 = shared)"
    )

    # Location
    location: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        doc="Physical location of resource (e.g., 'Garage', 'Second Floor Office')"
    )

    # Status
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether resource is currently available for reservation"
    )

    # Flexible metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    resource_metadata: Mapped[dict] = mapped_column(
        get_json_type(),
        nullable=False,
        default=dict,
        doc="Resource-specific attributes (color, seats, specs, etc.)"
    )

    # Relationships
    reservations: Mapped[list["ResourceReservation"]] = relationship(
        "ResourceReservation",
        back_populates="resource",
        doc="Reservations for this resource"
    )

    # Indexes
    __table_args__ = (
        Index("idx_resource_type", "resource_type"),
        Index("idx_resource_active", "active"),
        Index("idx_resource_deleted", "deleted_at"),
    )

    def __repr__(self) -> str:
        """String representation showing name and type."""
        return f"<Resource(name='{self.name}', type='{self.resource_type}', capacity={self.capacity})>"


class ResourceReservation(BaseModel):
    """
    Tracks resource bookings, optionally linked to events.

    Represents a time slot when a resource is reserved.
    Can be linked to an event or standalone (e.g., blocking time for maintenance).

    Key features:
    - Time-range booking (start_time, end_time)
    - Optional event linkage
    - Quantity tracking for resources with capacity > 1
    - Status workflow (proposed, confirmed, cancelled)
    """

    __tablename__ = "resource_reservations"

    # Resource and event linkage
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resources.id"),
        nullable=False,
        doc="Resource being reserved"
    )

    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("events.id"),
        nullable=True,
        doc="Event this reservation is for (NULL for standalone reservations)"
    )

    reserved_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=False,
        doc="Family member who made the reservation"
    )

    # Time range
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Reservation start time (UTC)"
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Reservation end time (UTC)"
    )

    # Quantity reserved (for resources with capacity > 1)
    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Number of capacity units reserved (typically 1)"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="proposed",
        doc="Reservation status: 'proposed', 'confirmed', 'cancelled'"
    )

    # Additional information
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Additional notes about the reservation"
    )

    # Relationships
    resource: Mapped["Resource"] = relationship(
        "Resource",
        back_populates="reservations",
        doc="Resource being reserved"
    )

    event: Mapped[Optional["Event"]] = relationship(
        "Event",
        back_populates="resource_reservations",
        doc="Event this reservation is linked to"
    )

    reserver: Mapped["FamilyMember"] = relationship(
        "FamilyMember",
        foreign_keys=[reserved_by],
        doc="Family member who made the reservation"
    )

    # Indexes for time-range queries (critical for performance)
    __table_args__ = (
        Index("idx_reservation_resource", "resource_id"),
        Index("idx_reservation_event", "event_id"),
        Index("idx_reservation_reserver", "reserved_by"),
        Index("idx_reservation_status", "status"),
        Index("idx_reservation_deleted", "deleted_at"),
        # Composite index for resource availability queries
        Index("idx_reservation_resource_time", "resource_id", "start_time", "end_time"),
        Index("idx_reservation_status_time", "status", "start_time", "end_time"),
    )

    def __repr__(self) -> str:
        """String representation showing resource and time range."""
        return f"<ResourceReservation(resource_id={self.resource_id}, start={self.start_time}, status='{self.status}')>"
