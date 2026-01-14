"""
Resource model.

Entities:
- Resource: Represents shared family resources (vehicles, rooms, equipment)

Note: Resource reservations are tracked via Google Calendar (each resource can have
its own calendar) rather than in the local database.
"""

from typing import Optional

from sqlalchemy import String, Text, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import BaseModel, get_json_type


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
    - Optional Google Calendar ID for availability tracking
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

    # Google Calendar ID for resource availability tracking
    google_calendar_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Google Calendar ID for tracking resource reservations"
    )

    # Flexible metadata
    resource_metadata: Mapped[dict] = mapped_column(
        get_json_type(),
        nullable=False,
        default=dict,
        doc="Resource-specific attributes (color, seats, specs, etc.)"
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
