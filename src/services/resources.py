"""
Resource availability service.

Provides functions for:
- Checking resource availability
- Finding available time slots
- Managing resource reservations
"""

from datetime import datetime, timedelta
from typing import Optional, Sequence
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session, joinedload

from src.models.resources import Resource, ResourceReservation


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
    conflicting_reservations: list[ResourceReservation]


def check_resource_availability(
    session: Session,
    resource_id: UUID,
    start: datetime,
    end: datetime,
    quantity_needed: int = 1,
    exclude_reservation_id: Optional[UUID] = None,
) -> ResourceAvailability:
    """
    Check if a resource is available during a time range.

    Handles resources with capacity > 1 (shared resources).

    Args:
        session: Database session
        resource_id: Resource to check
        start: Requested start time
        end: Requested end time
        quantity_needed: How much capacity is needed
        exclude_reservation_id: Reservation to exclude (for updates)

    Returns:
        ResourceAvailability with availability info
    """
    # Get the resource
    resource = session.get(Resource, resource_id)
    if not resource or resource.deleted_at or not resource.active:
        return ResourceAvailability(
            resource_id=resource_id,
            resource_name=resource.name if resource else "Unknown",
            total_capacity=0,
            is_available=False,
            available_capacity=0,
            conflicting_reservations=[],
        )

    # Find overlapping reservations
    conditions = [
        ResourceReservation.resource_id == resource_id,
        ResourceReservation.deleted_at.is_(None),
        ResourceReservation.status.in_(["confirmed", "proposed"]),
        ResourceReservation.start_time < end,
        ResourceReservation.end_time > start,
    ]

    if exclude_reservation_id:
        conditions.append(ResourceReservation.id != exclude_reservation_id)

    stmt = (
        select(ResourceReservation)
        .where(and_(*conditions))
        .options(joinedload(ResourceReservation.event))
        .order_by(ResourceReservation.start_time)
    )

    conflicting = list(session.scalars(stmt).all())

    # Calculate reserved capacity
    reserved_capacity = sum(r.quantity_reserved for r in conflicting)
    available_capacity = resource.capacity - reserved_capacity

    return ResourceAvailability(
        resource_id=resource_id,
        resource_name=resource.name,
        total_capacity=resource.capacity,
        is_available=available_capacity >= quantity_needed,
        available_capacity=max(0, available_capacity),
        conflicting_reservations=conflicting,
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

    # Filter by availability
    available = []
    for resource in all_resources:
        availability = check_resource_availability(
            session, resource.id, start, end, min_capacity
        )
        if availability.is_available:
            available.append(resource)

    return available


def get_resource_schedule(
    session: Session,
    resource_id: UUID,
    start: datetime,
    end: datetime,
) -> Sequence[ResourceReservation]:
    """
    Get all reservations for a resource within a time range.

    Args:
        session: Database session
        resource_id: Resource to query
        start: Range start
        end: Range end

    Returns:
        List of reservations
    """
    stmt = (
        select(ResourceReservation)
        .where(
            and_(
                ResourceReservation.resource_id == resource_id,
                ResourceReservation.deleted_at.is_(None),
                ResourceReservation.status.in_(["confirmed", "proposed"]),
                ResourceReservation.start_time < end,
                ResourceReservation.end_time > start,
            )
        )
        .options(
            joinedload(ResourceReservation.event),
            joinedload(ResourceReservation.reserver),
        )
        .order_by(ResourceReservation.start_time)
    )

    return session.scalars(stmt).all()


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
    resource = session.get(Resource, resource_id)
    if not resource or resource.deleted_at or not resource.active:
        return []

    # Define the day boundaries
    day_start = datetime(date.year, date.month, date.day, start_hour, 0, 0)
    day_end = datetime(date.year, date.month, date.day, end_hour, 0, 0)

    # Get existing reservations for the day
    reservations = get_resource_schedule(session, resource_id, day_start, day_end)

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


def get_resource_utilization(
    session: Session,
    resource_id: UUID,
    start: datetime,
    end: datetime,
) -> float:
    """
    Calculate resource utilization percentage for a time range.

    Args:
        session: Database session
        resource_id: Resource to analyze
        start: Range start
        end: Range end

    Returns:
        Utilization as a percentage (0.0 to 1.0)
    """
    resource = session.get(Resource, resource_id)
    if not resource or resource.deleted_at:
        return 0.0

    reservations = get_resource_schedule(session, resource_id, start, end)

    # Calculate total reserved time
    total_range = (end - start).total_seconds()
    if total_range <= 0:
        return 0.0

    reserved_seconds = 0.0
    for res in reservations:
        # Clip reservation to the query range
        res_start = max(res.start_time, start)
        res_end = min(res.end_time, end)
        if res_end > res_start:
            reserved_seconds += (res_end - res_start).total_seconds()

    return min(1.0, reserved_seconds / total_range)


def get_resources_by_type(
    session: Session,
    resource_type: str,
    active_only: bool = True,
) -> Sequence[Resource]:
    """
    Get all resources of a specific type.

    Args:
        session: Database session
        resource_type: Type to filter by
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
