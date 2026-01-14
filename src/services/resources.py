"""
Resource availability service.

Provides functions for:
- Querying resources from the database
- Checking resource availability via Google Calendar (if configured)

Note: Resource reservations are tracked via Google Calendar.
Each resource can have a google_calendar_id for availability tracking.
"""

from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.models.resources import Resource


@dataclass
class AvailabilitySlot:
    """Represents an available time slot for a resource."""

    start: datetime
    end: datetime
    available_capacity: int


@dataclass
class ResourceAvailability:
    """Resource availability information for a time range."""

    resource_id: UUID
    resource_name: str
    total_capacity: int
    is_available: bool
    available_capacity: int
    has_calendar: bool  # True if resource has a Google Calendar for tracking


def get_resource_by_id(
    session: Session,
    resource_id: UUID,
) -> Optional[Resource]:
    """
    Get a resource by ID.

    Args:
        session: Database session
        resource_id: Resource ID

    Returns:
        Resource or None
    """
    resource = session.get(Resource, resource_id)
    if resource and resource.deleted_at is None:
        return resource
    return None


def get_all_resources(
    session: Session,
    active_only: bool = True,
) -> Sequence[Resource]:
    """
    Get all resources.

    Args:
        session: Database session
        active_only: Only return active resources

    Returns:
        List of resources
    """
    conditions = [Resource.deleted_at.is_(None)]
    if active_only:
        conditions.append(Resource.active.is_(True))

    stmt = (
        select(Resource)
        .where(and_(*conditions))
        .order_by(Resource.name)
    )

    return session.scalars(stmt).all()


def get_resources_by_type(
    session: Session,
    resource_type: str,
    active_only: bool = True,
) -> Sequence[Resource]:
    """
    Get all resources of a specific type.

    Args:
        session: Database session
        resource_type: Type to filter by (vehicle, room, equipment, other)
        active_only: Only return active resources

    Returns:
        List of resources
    """
    conditions = [
        Resource.deleted_at.is_(None),
        Resource.resource_type == resource_type,
    ]

    if active_only:
        conditions.append(Resource.active.is_(True))

    stmt = (
        select(Resource)
        .where(and_(*conditions))
        .order_by(Resource.name)
    )

    return session.scalars(stmt).all()


def find_resources_with_calendar(
    session: Session,
    active_only: bool = True,
) -> Sequence[Resource]:
    """
    Find resources that have a Google Calendar for availability tracking.

    Args:
        session: Database session
        active_only: Only return active resources

    Returns:
        List of resources with google_calendar_id set
    """
    conditions = [
        Resource.deleted_at.is_(None),
        Resource.google_calendar_id.isnot(None),
    ]

    if active_only:
        conditions.append(Resource.active.is_(True))

    stmt = (
        select(Resource)
        .where(and_(*conditions))
        .order_by(Resource.name)
    )

    return session.scalars(stmt).all()


def check_resource_availability(
    session: Session,
    resource_id: UUID,
    start: datetime,
    end: datetime,
    quantity_needed: int = 1,
) -> ResourceAvailability:
    """
    Check if a resource is available during a time range.

    For resources with a google_calendar_id, use CalendarService to check
    actual availability via Google Calendar. For resources without a calendar,
    this returns basic availability based on the resource being active.

    Args:
        session: Database session
        resource_id: Resource to check
        start: Requested start time
        end: Requested end time
        quantity_needed: How much capacity is needed

    Returns:
        ResourceAvailability with availability info
    """
    resource = get_resource_by_id(session, resource_id)

    if not resource or not resource.active:
        return ResourceAvailability(
            resource_id=resource_id,
            resource_name=resource.name if resource else "Unknown",
            total_capacity=0,
            is_available=False,
            available_capacity=0,
            has_calendar=False,
        )

    has_calendar = resource.google_calendar_id is not None

    # If resource has a calendar, check Google Calendar for availability
    if has_calendar:
        try:
            from src.services.calendar_service import get_calendar_service

            calendar_service = get_calendar_service()
            busy_slots = calendar_service.find_free_busy(
                [resource.google_calendar_id],
                start,
                end,
            )

            # If there are busy slots for this calendar, it's not available
            resource_busy = busy_slots.get(resource.google_calendar_id, [])
            is_available = len(resource_busy) == 0

            return ResourceAvailability(
                resource_id=resource_id,
                resource_name=resource.name,
                total_capacity=resource.capacity,
                is_available=is_available and resource.capacity >= quantity_needed,
                available_capacity=resource.capacity if is_available else 0,
                has_calendar=True,
            )
        except Exception:
            # If calendar check fails, fall back to assuming available
            pass

    # Resource without calendar - assume available if active
    return ResourceAvailability(
        resource_id=resource_id,
        resource_name=resource.name,
        total_capacity=resource.capacity,
        is_available=resource.capacity >= quantity_needed,
        available_capacity=resource.capacity,
        has_calendar=has_calendar,
    )


def check_multiple_resources(
    session: Session,
    resource_ids: list[UUID],
    start: datetime,
    end: datetime,
) -> dict[UUID, ResourceAvailability]:
    """
    Check availability of multiple resources at once.

    Args:
        session: Database session
        resource_ids: Resources to check
        start: Requested start time
        end: Requested end time

    Returns:
        Dict mapping resource_id to availability info
    """
    return {
        rid: check_resource_availability(session, rid, start, end)
        for rid in resource_ids
    }


def find_available_resources(
    session: Session,
    resource_type: Optional[str] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    min_capacity: int = 1,
) -> Sequence[Resource]:
    """
    Find resources that are available during a time range.

    Args:
        session: Database session
        resource_type: Filter by type (vehicle, room, equipment, etc.)
        start: Time range start (None = don't filter by time)
        end: Time range end
        min_capacity: Minimum required capacity

    Returns:
        List of available resources
    """
    # First get all active resources matching criteria
    conditions = [
        Resource.deleted_at.is_(None),
        Resource.active.is_(True),
        Resource.capacity >= min_capacity,
    ]

    if resource_type:
        conditions.append(Resource.resource_type == resource_type)

    stmt = select(Resource).where(and_(*conditions)).order_by(Resource.name)
    all_resources = list(session.scalars(stmt).all())

    # If no time range, return all matching resources
    if start is None or end is None:
        return all_resources

    # Filter by availability using calendar check
    available = []
    for resource in all_resources:
        availability = check_resource_availability(
            session, resource.id, start, end, min_capacity
        )
        if availability.is_available:
            available.append(resource)

    return available


def find_available_slots(
    session: Session,
    resource_id: UUID,
    date: datetime,
    duration: timedelta,
    start_hour: int = 8,
    end_hour: int = 20,
    slot_interval: timedelta = timedelta(minutes=30),
) -> list[AvailabilitySlot]:
    """
    Find available time slots for a resource on a given day.

    Args:
        session: Database session
        resource_id: Resource to check
        date: Date to check
        duration: Required duration for reservation
        start_hour: Earliest slot start (default 8am)
        end_hour: Latest slot end (default 8pm)
        slot_interval: Time between slot starts (default 30min)

    Returns:
        List of available slots
    """
    resource = get_resource_by_id(session, resource_id)
    if not resource or not resource.active:
        return []

    # Define the day boundaries
    day_start = datetime(date.year, date.month, date.day, start_hour, 0, 0)
    day_end = datetime(date.year, date.month, date.day, end_hour, 0, 0)

    # Generate potential slots
    available_slots = []
    current = day_start

    while current + duration <= day_end:
        slot_end = current + duration

        # Check if this slot is available
        availability = check_resource_availability(
            session, resource_id, current, slot_end
        )

        if availability.is_available:
            available_slots.append(
                AvailabilitySlot(
                    start=current,
                    end=slot_end,
                    available_capacity=availability.available_capacity,
                )
            )

        current += slot_interval

    return available_slots
