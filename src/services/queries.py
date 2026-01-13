"""
Query service for events and calendars.

Provides common query patterns with:
- Eager loading to avoid N+1 queries
- Time-range filtering
- Soft deletion handling
- Conflict detection queries
"""

from datetime import datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, selectinload, joinedload

from src.models.events import Event, EventParticipant
from src.models.family import FamilyMember, Calendar
from src.models.resources import Resource, ResourceReservation
from src.models.conflicts import Conflict


# =============================================================================
# Event Queries
# =============================================================================


def get_events_in_range(
    session: Session,
    calendar_id: UUID,
    start: datetime,
    end: datetime,
    include_proposed: bool = True,
    include_cancelled: bool = False,
) -> Sequence[Event]:
    """
    Get all events within a time range for a calendar.

    Args:
        session: Database session
        calendar_id: Calendar to query
        start: Range start (inclusive)
        end: Range end (inclusive)
        include_proposed: Include proposed (unconfirmed) events
        include_cancelled: Include cancelled events

    Returns:
        List of events with participants and reservations eagerly loaded
    """
    # Build status filter
    statuses = ["confirmed"]
    if include_proposed:
        statuses.append("proposed")
    if include_cancelled:
        statuses.append("cancelled")

    stmt = (
        select(Event)
        .where(
            and_(
                Event.calendar_id == calendar_id,
                Event.deleted_at.is_(None),
                Event.status.in_(statuses),
                # Events that overlap with the range
                Event.start_time < end,
                Event.end_time > start,
            )
        )
        .options(
            selectinload(Event.participants).selectinload(EventParticipant.family_member),
            selectinload(Event.resource_reservations).selectinload(ResourceReservation.resource),
        )
        .order_by(Event.start_time)
    )

    return session.scalars(stmt).all()


def get_events_for_member(
    session: Session,
    member_id: UUID,
    start: datetime,
    end: datetime,
    include_proposed: bool = True,
) -> Sequence[Event]:
    """
    Get all events a family member is participating in within a time range.

    Args:
        session: Database session
        member_id: Family member ID
        start: Range start
        end: Range end
        include_proposed: Include proposed events

    Returns:
        List of events the member is participating in
    """
    statuses = ["confirmed"]
    if include_proposed:
        statuses.append("proposed")

    stmt = (
        select(Event)
        .join(EventParticipant)
        .where(
            and_(
                EventParticipant.family_member_id == member_id,
                Event.deleted_at.is_(None),
                Event.status.in_(statuses),
                Event.start_time < end,
                Event.end_time > start,
            )
        )
        .options(
            selectinload(Event.participants),
            selectinload(Event.calendar),
        )
        .order_by(Event.start_time)
    )

    return session.scalars(stmt).all()


def get_event_by_id(
    session: Session,
    event_id: UUID,
    include_deleted: bool = False,
) -> Optional[Event]:
    """
    Get a single event by ID with all relationships loaded.

    Args:
        session: Database session
        event_id: Event ID
        include_deleted: Include soft-deleted events

    Returns:
        Event or None
    """
    conditions = [Event.id == event_id]
    if not include_deleted:
        conditions.append(Event.deleted_at.is_(None))

    stmt = (
        select(Event)
        .where(and_(*conditions))
        .options(
            selectinload(Event.participants).selectinload(EventParticipant.family_member),
            selectinload(Event.resource_reservations).selectinload(ResourceReservation.resource),
            joinedload(Event.calendar),
            joinedload(Event.creator),
        )
    )

    return session.scalar(stmt)


def find_overlapping_events(
    session: Session,
    calendar_id: UUID,
    start: datetime,
    end: datetime,
    exclude_event_id: Optional[UUID] = None,
) -> Sequence[Event]:
    """
    Find events that overlap with a given time range.

    Used for conflict detection.

    Args:
        session: Database session
        calendar_id: Calendar to check
        start: Proposed start time
        end: Proposed end time
        exclude_event_id: Event to exclude (for updates)

    Returns:
        List of overlapping events
    """
    conditions = [
        Event.calendar_id == calendar_id,
        Event.deleted_at.is_(None),
        Event.status.in_(["confirmed", "proposed"]),
        # Overlap condition: event starts before we end AND ends after we start
        Event.start_time < end,
        Event.end_time > start,
    ]

    if exclude_event_id:
        conditions.append(Event.id != exclude_event_id)

    stmt = (
        select(Event)
        .where(and_(*conditions))
        .options(selectinload(Event.participants))
        .order_by(Event.start_time)
    )

    return session.scalars(stmt).all()


def get_upcoming_events(
    session: Session,
    calendar_id: UUID,
    limit: int = 10,
    after: Optional[datetime] = None,
) -> Sequence[Event]:
    """
    Get upcoming events for a calendar.

    Args:
        session: Database session
        calendar_id: Calendar to query
        limit: Maximum events to return
        after: Start from this time (default: now)

    Returns:
        List of upcoming events
    """
    if after is None:
        after = datetime.utcnow()

    stmt = (
        select(Event)
        .where(
            and_(
                Event.calendar_id == calendar_id,
                Event.deleted_at.is_(None),
                Event.status == "confirmed",
                Event.start_time >= after,
            )
        )
        .options(
            selectinload(Event.participants).selectinload(EventParticipant.family_member),
        )
        .order_by(Event.start_time)
        .limit(limit)
    )

    return session.scalars(stmt).all()


# =============================================================================
# Family Member Queries
# =============================================================================


def get_member_schedule(
    session: Session,
    member_id: UUID,
    date: datetime,
) -> Sequence[Event]:
    """
    Get a family member's schedule for a specific day.

    Args:
        session: Database session
        member_id: Family member ID
        date: Date to query (uses date part only)

    Returns:
        List of events for that day
    """
    day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
    day_end = datetime(date.year, date.month, date.day, 23, 59, 59)

    return get_events_for_member(session, member_id, day_start, day_end)


def find_busy_members(
    session: Session,
    member_ids: list[UUID],
    start: datetime,
    end: datetime,
) -> list[UUID]:
    """
    Find which members are busy during a time slot.

    Args:
        session: Database session
        member_ids: Members to check
        start: Time slot start
        end: Time slot end

    Returns:
        List of member IDs who have conflicts
    """
    stmt = (
        select(EventParticipant.family_member_id)
        .join(Event)
        .where(
            and_(
                EventParticipant.family_member_id.in_(member_ids),
                Event.deleted_at.is_(None),
                Event.status.in_(["confirmed", "proposed"]),
                Event.start_time < end,
                Event.end_time > start,
            )
        )
        .distinct()
    )

    return list(session.scalars(stmt).all())


def find_available_members(
    session: Session,
    member_ids: list[UUID],
    start: datetime,
    end: datetime,
) -> list[UUID]:
    """
    Find which members are available during a time slot.

    Args:
        session: Database session
        member_ids: Members to check
        start: Time slot start
        end: Time slot end

    Returns:
        List of available member IDs
    """
    busy = set(find_busy_members(session, member_ids, start, end))
    return [mid for mid in member_ids if mid not in busy]


# =============================================================================
# Conflict Queries
# =============================================================================


def get_unresolved_conflicts(
    session: Session,
    event_id: Optional[UUID] = None,
) -> Sequence[Conflict]:
    """
    Get unresolved conflicts, optionally for a specific event.

    Args:
        session: Database session
        event_id: Optional event to filter by

    Returns:
        List of unresolved conflicts
    """
    conditions = [
        Conflict.deleted_at.is_(None),
        Conflict.status == "detected",  # Unresolved conflicts have status 'detected'
    ]

    if event_id:
        conditions.append(
            or_(
                Conflict.proposed_event_id == event_id,
                Conflict.conflicting_event_id == event_id,
            )
        )

    stmt = (
        select(Conflict)
        .where(and_(*conditions))
        .options(
            joinedload(Conflict.proposed_event),
            joinedload(Conflict.conflicting_event),
        )
        .order_by(Conflict.created_at.desc())
    )

    return session.scalars(stmt).all()


# =============================================================================
# Calendar Queries
# =============================================================================


def get_calendars_by_owner(
    session: Session,
    owner_id: UUID,
) -> Sequence[Calendar]:
    """
    Get all calendars owned by a family member.

    Args:
        session: Database session
        owner_id: Owner's family member ID

    Returns:
        List of calendars with owners loaded
    """
    stmt = (
        select(Calendar)
        .where(
            and_(
                Calendar.owner_id == owner_id,
                Calendar.deleted_at.is_(None),
            )
        )
        .options(joinedload(Calendar.owner))
        .order_by(Calendar.name)
    )

    return session.scalars(stmt).all()


def get_calendar_by_id(
    session: Session,
    calendar_id: UUID,
) -> Optional[Calendar]:
    """
    Get a calendar by ID with events count.

    Args:
        session: Database session
        calendar_id: Calendar ID

    Returns:
        Calendar or None
    """
    stmt = (
        select(Calendar)
        .where(
            and_(
                Calendar.id == calendar_id,
                Calendar.deleted_at.is_(None),
            )
        )
        .options(
            joinedload(Calendar.owner),
        )
    )

    return session.scalar(stmt)
