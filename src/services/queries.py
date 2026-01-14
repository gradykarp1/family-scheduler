"""
Query service for family configuration data.

Provides common query patterns for:
- Family members and their preferences
- Calendars and their configuration
- Resources and their metadata
- Constraints

Note: Events are stored in Google Calendar, not the local database.
Use CalendarService for event queries.
"""

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import Session, selectinload, joinedload

from src.models.family import FamilyMember, Calendar
from src.models.resources import Resource
from src.models.constraints import Constraint


# =============================================================================
# Family Member Queries
# =============================================================================


def get_all_family_members(
    session: Session,
    include_deleted: bool = False,
) -> Sequence[FamilyMember]:
    """
    Get all family members.

    Args:
        session: Database session
        include_deleted: Include soft-deleted members

    Returns:
        List of family members with calendars loaded
    """
    conditions = []
    if not include_deleted:
        conditions.append(FamilyMember.deleted_at.is_(None))

    stmt = (
        select(FamilyMember)
        .where(and_(*conditions)) if conditions else select(FamilyMember)
    )

    if conditions:
        stmt = (
            select(FamilyMember)
            .where(and_(*conditions))
            .options(
                selectinload(FamilyMember.owned_calendars),
                joinedload(FamilyMember.default_calendar),
            )
            .order_by(FamilyMember.name)
        )
    else:
        stmt = (
            select(FamilyMember)
            .options(
                selectinload(FamilyMember.owned_calendars),
                joinedload(FamilyMember.default_calendar),
            )
            .order_by(FamilyMember.name)
        )

    return session.scalars(stmt).all()


def get_family_member_by_id(
    session: Session,
    member_id: UUID,
    include_deleted: bool = False,
) -> Optional[FamilyMember]:
    """
    Get a family member by ID.

    Args:
        session: Database session
        member_id: Family member ID
        include_deleted: Include soft-deleted members

    Returns:
        FamilyMember or None
    """
    conditions = [FamilyMember.id == member_id]
    if not include_deleted:
        conditions.append(FamilyMember.deleted_at.is_(None))

    stmt = (
        select(FamilyMember)
        .where(and_(*conditions))
        .options(
            selectinload(FamilyMember.owned_calendars),
            joinedload(FamilyMember.default_calendar),
            selectinload(FamilyMember.constraints),
        )
    )

    return session.scalar(stmt)


def get_family_member_by_email(
    session: Session,
    email: str,
) -> Optional[FamilyMember]:
    """
    Get a family member by email address.

    Args:
        session: Database session
        email: Email address

    Returns:
        FamilyMember or None
    """
    stmt = (
        select(FamilyMember)
        .where(
            and_(
                FamilyMember.email == email,
                FamilyMember.deleted_at.is_(None),
            )
        )
        .options(
            joinedload(FamilyMember.default_calendar),
        )
    )

    return session.scalar(stmt)


def get_family_members_by_role(
    session: Session,
    role: str,
) -> Sequence[FamilyMember]:
    """
    Get family members by role (parent, child, other).

    Args:
        session: Database session
        role: Role to filter by

    Returns:
        List of family members with that role
    """
    stmt = (
        select(FamilyMember)
        .where(
            and_(
                FamilyMember.role == role,
                FamilyMember.deleted_at.is_(None),
            )
        )
        .order_by(FamilyMember.name)
    )

    return session.scalars(stmt).all()


# =============================================================================
# Calendar Queries
# =============================================================================


def get_all_calendars(
    session: Session,
    include_deleted: bool = False,
) -> Sequence[Calendar]:
    """
    Get all calendars.

    Args:
        session: Database session
        include_deleted: Include soft-deleted calendars

    Returns:
        List of calendars with owners loaded
    """
    conditions = []
    if not include_deleted:
        conditions.append(Calendar.deleted_at.is_(None))

    if conditions:
        stmt = (
            select(Calendar)
            .where(and_(*conditions))
            .options(joinedload(Calendar.owner))
            .order_by(Calendar.name)
        )
    else:
        stmt = (
            select(Calendar)
            .options(joinedload(Calendar.owner))
            .order_by(Calendar.name)
        )

    return session.scalars(stmt).all()


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
    Get a calendar by ID.

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


def get_calendar_by_google_id(
    session: Session,
    google_calendar_id: str,
) -> Optional[Calendar]:
    """
    Get a calendar by its Google Calendar ID.

    Args:
        session: Database session
        google_calendar_id: Google Calendar ID

    Returns:
        Calendar or None
    """
    stmt = (
        select(Calendar)
        .where(
            and_(
                Calendar.google_calendar_id == google_calendar_id,
                Calendar.deleted_at.is_(None),
            )
        )
        .options(
            joinedload(Calendar.owner),
        )
    )

    return session.scalar(stmt)


def get_calendars_by_type(
    session: Session,
    calendar_type: str,
) -> Sequence[Calendar]:
    """
    Get calendars by type (personal, family, shared).

    Args:
        session: Database session
        calendar_type: Calendar type to filter by

    Returns:
        List of calendars of that type
    """
    stmt = (
        select(Calendar)
        .where(
            and_(
                Calendar.calendar_type == calendar_type,
                Calendar.deleted_at.is_(None),
            )
        )
        .options(joinedload(Calendar.owner))
        .order_by(Calendar.name)
    )

    return session.scalars(stmt).all()


# =============================================================================
# Resource Queries
# =============================================================================


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
    stmt = (
        select(Resource)
        .where(
            and_(
                Resource.id == resource_id,
                Resource.deleted_at.is_(None),
            )
        )
    )

    return session.scalar(stmt)


def get_resources_by_type(
    session: Session,
    resource_type: str,
    active_only: bool = True,
) -> Sequence[Resource]:
    """
    Get resources by type (vehicle, room, equipment, other).

    Args:
        session: Database session
        resource_type: Resource type to filter by
        active_only: Only return active resources

    Returns:
        List of resources of that type
    """
    conditions = [
        Resource.resource_type == resource_type,
        Resource.deleted_at.is_(None),
    ]
    if active_only:
        conditions.append(Resource.active.is_(True))

    stmt = (
        select(Resource)
        .where(and_(*conditions))
        .order_by(Resource.name)
    )

    return session.scalars(stmt).all()


# =============================================================================
# Constraint Queries
# =============================================================================


def get_all_constraints(
    session: Session,
    active_only: bool = True,
) -> Sequence[Constraint]:
    """
    Get all constraints.

    Args:
        session: Database session
        active_only: Only return active constraints

    Returns:
        List of constraints with family members loaded
    """
    conditions = [Constraint.deleted_at.is_(None)]
    if active_only:
        conditions.append(Constraint.active.is_(True))

    stmt = (
        select(Constraint)
        .where(and_(*conditions))
        .options(joinedload(Constraint.family_member))
        .order_by(Constraint.priority.desc())
    )

    return session.scalars(stmt).all()


def get_constraints_for_member(
    session: Session,
    member_id: UUID,
    active_only: bool = True,
) -> Sequence[Constraint]:
    """
    Get all constraints for a specific family member.

    Args:
        session: Database session
        member_id: Family member ID
        active_only: Only return active constraints

    Returns:
        List of constraints for that member
    """
    conditions = [
        Constraint.family_member_id == member_id,
        Constraint.deleted_at.is_(None),
    ]
    if active_only:
        conditions.append(Constraint.active.is_(True))

    stmt = (
        select(Constraint)
        .where(and_(*conditions))
        .order_by(Constraint.priority.desc())
    )

    return session.scalars(stmt).all()


def get_constraints_by_type(
    session: Session,
    constraint_type: str,
    active_only: bool = True,
) -> Sequence[Constraint]:
    """
    Get constraints by type.

    Args:
        session: Database session
        constraint_type: Constraint type to filter by
        active_only: Only return active constraints

    Returns:
        List of constraints of that type
    """
    conditions = [
        Constraint.constraint_type == constraint_type,
        Constraint.deleted_at.is_(None),
    ]
    if active_only:
        conditions.append(Constraint.active.is_(True))

    stmt = (
        select(Constraint)
        .where(and_(*conditions))
        .options(joinedload(Constraint.family_member))
        .order_by(Constraint.priority.desc())
    )

    return session.scalars(stmt).all()
