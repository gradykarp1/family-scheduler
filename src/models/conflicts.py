"""
Conflict model.

Entities:
- Conflict: Tracks detected scheduling conflicts and their resolutions
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import BaseModel, get_json_type

# Avoid circular imports for type hints
if TYPE_CHECKING:
    from src.models.events import Event


class Conflict(BaseModel):
    """
    Tracks detected scheduling conflicts and their resolutions.

    Conflict types:
    - time_conflict: Participant double-booked or insufficient gap
    - resource_conflict: Resource at/over capacity
    - constraint_violation: Hard constraint blocked or soft constraint suboptimal

    Lifecycle:
    1. detected: Conflict identified by Conflict Detection Agent
    2. resolved: User or system resolved the conflict
    3. ignored: User chose to proceed despite conflict

    Resolution methods:
    - user_manual: User manually resolved
    - auto_confirm: System auto-confirmed (soft constraint only)
    - agent_suggested: User selected an agent-proposed resolution
    """

    __tablename__ = "conflicts"

    # Conflict identification
    proposed_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        doc="The proposed event that triggered this conflict"
    )

    conflicting_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("events.id"),
        nullable=True,
        doc="The existing event that conflicts (NULL for constraint violations)"
    )

    # Conflict classification
    conflict_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Conflict type: 'time_conflict', 'resource_conflict', 'constraint_violation'"
    )

    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Severity: 'low', 'medium', 'high', 'critical'"
    )

    # Conflict description
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Human-readable conflict description"
    )

    # Affected entities (stored as JSON arrays)
    affected_participants: Mapped[list] = mapped_column(
        get_json_type(),
        nullable=False,
        default=list,
        doc="List of affected family member IDs"
    )

    affected_resources: Mapped[Optional[list]] = mapped_column(
        get_json_type(),
        nullable=True,
        doc="List of affected resource IDs (NULL if not resource-related)"
    )

    affected_constraints: Mapped[Optional[list]] = mapped_column(
        get_json_type(),
        nullable=True,
        doc="List of violated constraint IDs (NULL if not constraint-related)"
    )

    # Resolution data
    proposed_resolutions: Mapped[Optional[dict]] = mapped_column(
        get_json_type(),
        nullable=True,
        doc="Resolution strategies proposed by Resolution Agent"
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="detected",
        doc="Status: 'detected', 'resolved', 'ignored'"
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        doc="Timestamp when conflict was detected (UTC)"
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when conflict was resolved (UTC)"
    )

    resolution_applied: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Resolution strategy that was applied (resolution_id from proposed_resolutions)"
    )

    resolution_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Resolution method: 'user_manual', 'auto_confirm', 'agent_suggested'"
    )

    # Additional notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Additional notes about the conflict or resolution"
    )

    # Relationships
    proposed_event: Mapped["Event"] = relationship(
        "Event",
        foreign_keys=[proposed_event_id],
        back_populates="proposed_conflicts",
        doc="The proposed event that triggered this conflict"
    )

    conflicting_event: Mapped[Optional["Event"]] = relationship(
        "Event",
        foreign_keys=[conflicting_event_id],
        back_populates="conflicting_with",
        doc="The existing event that conflicts (if applicable)"
    )

    # Indexes
    __table_args__ = (
        Index("idx_conflict_proposed_event", "proposed_event_id"),
        Index("idx_conflict_conflicting_event", "conflicting_event_id"),
        Index("idx_conflict_type", "conflict_type"),
        Index("idx_conflict_severity", "severity"),
        Index("idx_conflict_status", "status"),
        Index("idx_conflict_detected_at", "detected_at"),
        Index("idx_conflict_deleted", "deleted_at"),
        # Composite index for active conflict queries
        Index("idx_conflict_status_detected", "status", "detected_at"),
    )

    def __repr__(self) -> str:
        """String representation showing type and status."""
        return f"<Conflict(type='{self.conflict_type}', severity='{self.severity}', status='{self.status}')>"
