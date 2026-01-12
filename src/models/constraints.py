"""
Constraint model.

Entities:
- Constraint: Represents rules and preferences that guide scheduling
"""

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel, get_json_type

# Avoid circular imports for type hints
if TYPE_CHECKING:
    from src.models.family import FamilyMember


class Constraint(BaseModel):
    """
    Represents scheduling rules and preferences.

    Constraints can be:
    - Hard: Blocking constraints that must be satisfied
    - Soft: Preferences that influence scoring but don't block

    Types of constraints:
    - time_window: Preferred or blocked time windows
    - min_gap: Minimum time between events
    - max_events_per_day: Limit on daily event count
    - resource_priority: Resource usage preferences
    - custom: Arbitrary constraint rules

    The flexible rule structure (JSON) allows for diverse constraint types
    without schema changes.
    """

    __tablename__ = "constraints"

    # Constraint identification
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable constraint name (e.g., 'No early morning events')"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Detailed description of the constraint"
    )

    # Ownership
    family_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("family_members.id"),
        nullable=True,
        doc="Family member this constraint applies to (NULL for family-wide constraints)"
    )

    # Constraint type and level
    constraint_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Constraint type: 'time_window', 'min_gap', 'max_events_per_day', 'resource_priority', 'custom'"
    )

    level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Constraint level: 'hard' (blocking) or 'soft' (preference)"
    )

    # Priority (for soft constraints)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        doc="Priority for soft constraints (1-10: 1=low, 5=medium, 10=high)"
    )

    # Flexible constraint rule definition
    rule: Mapped[dict] = mapped_column(
        get_json_type(),
        nullable=False,
        doc="Constraint rule definition (structure varies by constraint_type)"
    )

    # Time window fields (denormalized for query optimization)
    time_window_start: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
        doc="Start of time window in HH:MM format (e.g., '09:00')"
    )

    time_window_end: Mapped[Optional[str]] = mapped_column(
        String(5),
        nullable=True,
        doc="End of time window in HH:MM format (e.g., '17:00')"
    )

    # Day-based constraints
    days_of_week: Mapped[Optional[list]] = mapped_column(
        get_json_type(),
        nullable=True,
        doc="List of day numbers (0=Monday, 6=Sunday) this constraint applies to"
    )

    specific_date: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        doc="Specific date in YYYY-MM-DD format (for one-time constraints)"
    )

    # Status
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this constraint is currently active"
    )

    # Relationships
    family_member: Mapped[Optional["FamilyMember"]] = relationship(
        "FamilyMember",
        back_populates="constraints",
        doc="Family member this constraint applies to"
    )

    # Indexes
    __table_args__ = (
        Index("idx_constraint_member", "family_member_id"),
        Index("idx_constraint_type", "constraint_type"),
        Index("idx_constraint_level", "level"),
        Index("idx_constraint_active", "active"),
        Index("idx_constraint_deleted", "deleted_at"),
        # Composite index for filtering active constraints by member
        Index("idx_constraint_member_active", "family_member_id", "active"),
    )

    def __repr__(self) -> str:
        """String representation showing name and level."""
        return f"<Constraint(name='{self.name}', level='{self.level}', type='{self.constraint_type}')>"
