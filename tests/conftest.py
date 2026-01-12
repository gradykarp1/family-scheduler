"""
Pytest configuration and fixtures for Family Scheduler tests.

Provides database session fixtures and sample data for testing.
"""

import uuid
from datetime import datetime, timezone
from typing import Generator

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
from src.models.family import FamilyMember, Calendar
from src.models.events import Event, EventParticipant
from src.models.resources import Resource, ResourceReservation
from src.models.constraints import Constraint
from src.models.conflicts import Conflict


# Configure SQLite to enforce foreign key constraints in tests
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a clean database session for each test.

    Uses an in-memory SQLite database that is torn down after each test.
    All changes are rolled back, ensuring test isolation.

    Yields:
        Session: SQLAlchemy session for database operations
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # Disable foreign key constraints for drop operations
        with engine.begin() as connection:
            connection.execute(sa.text("PRAGMA foreign_keys=OFF"))
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def sample_family_member(db_session: Session) -> FamilyMember:
    """
    Create a sample FamilyMember for testing.

    Returns:
        FamilyMember: A persisted family member with default values
    """
    member = FamilyMember(
        name="John Doe",
        email="john.doe@example.com",
        role="parent",
        preferences={
            "timezone": "America/Los_Angeles",
            "work_hours": {"start": "09:00", "end": "17:00"}
        }
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member


@pytest.fixture
def sample_calendar(db_session: Session, sample_family_member: FamilyMember) -> Calendar:
    """
    Create a sample Calendar for testing.

    Args:
        db_session: Database session
        sample_family_member: Owner of the calendar

    Returns:
        Calendar: A persisted calendar
    """
    calendar = Calendar(
        name="Family Calendar",
        description="Main family calendar",
        calendar_type="family",
        color="#FF5733",
        owner_id=sample_family_member.id,
        visibility="shared"
    )
    db_session.add(calendar)
    db_session.commit()
    db_session.refresh(calendar)
    return calendar


@pytest.fixture
def sample_event(db_session: Session, sample_calendar: Calendar, sample_family_member: FamilyMember) -> Event:
    """
    Create a sample Event for testing.

    Args:
        db_session: Database session
        sample_calendar: Calendar the event belongs to
        sample_family_member: Creator of the event

    Returns:
        Event: A persisted event
    """
    event = Event(
        calendar_id=sample_calendar.id,
        title="Doctor Appointment",
        description="Annual checkup",
        start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
        all_day=False,
        location="Medical Center",
        status="proposed",
        priority="medium",
        flexibility="fixed",
        created_by=sample_family_member.id,
        event_metadata={"reminder": "1 day before"}
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def sample_resource(db_session: Session) -> Resource:
    """
    Create a sample Resource for testing.

    Returns:
        Resource: A persisted resource
    """
    resource = Resource(
        name="Family Car",
        description="Honda Accord",
        resource_type="vehicle",
        capacity=1,
        location="Garage",
        active=True,
        resource_metadata={
            "color": "blue",
            "seats": 5,
            "license_plate": "ABC123"
        }
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


@pytest.fixture
def sample_constraint(db_session: Session, sample_family_member: FamilyMember) -> Constraint:
    """
    Create a sample Constraint for testing.

    Args:
        db_session: Database session
        sample_family_member: Family member the constraint applies to

    Returns:
        Constraint: A persisted constraint
    """
    constraint = Constraint(
        name="Work Hours",
        description="No events during work hours",
        family_member_id=sample_family_member.id,
        constraint_type="availability",
        level="hard",
        priority=10,
        rule={
            "type": "time_window",
            "start": "09:00",
            "end": "17:00"
        },
        time_window_start="09:00",
        time_window_end="17:00",
        days_of_week=["monday", "tuesday", "wednesday", "thursday", "friday"],
        active=True
    )
    db_session.add(constraint)
    db_session.commit()
    db_session.refresh(constraint)
    return constraint


@pytest.fixture
def sample_conflict(db_session: Session, sample_event: Event) -> Conflict:
    """
    Create a sample Conflict for testing.

    Args:
        db_session: Database session
        sample_event: Proposed event with conflict

    Returns:
        Conflict: A persisted conflict
    """
    # Create a second event that conflicts with the first
    conflicting_event = Event(
        calendar_id=sample_event.calendar_id,
        title="Team Meeting",
        description="Weekly sync",
        start_time=datetime(2026, 2, 15, 10, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 15, 11, 30, tzinfo=timezone.utc),
        all_day=False,
        status="confirmed",
        priority="high",
        flexibility="fixed",
        created_by=sample_event.created_by,
        event_metadata={}
    )
    db_session.add(conflicting_event)
    db_session.commit()
    db_session.refresh(conflicting_event)

    conflict = Conflict(
        proposed_event_id=sample_event.id,
        conflicting_event_id=conflicting_event.id,
        conflict_type="time_overlap",
        severity="high",
        description="Events overlap in time",
        affected_participants=[str(sample_event.created_by)],
        affected_resources=[],
        affected_constraints=[],
        proposed_resolutions=[
            {
                "type": "reschedule",
                "description": "Move doctor appointment to 1pm",
                "confidence": 0.85
            }
        ],
        status="detected"
    )
    db_session.add(conflict)
    db_session.commit()
    db_session.refresh(conflict)
    return conflict


@pytest.fixture
def multiple_family_members(db_session: Session) -> list[FamilyMember]:
    """
    Create multiple family members for testing relationships.

    Returns:
        list[FamilyMember]: List of persisted family members
    """
    members = [
        FamilyMember(
            name="Alice Parent",
            email="alice@example.com",
            role="parent",
            preferences={"timezone": "America/Los_Angeles"}
        ),
        FamilyMember(
            name="Bob Parent",
            email="bob@example.com",
            role="parent",
            preferences={"timezone": "America/Los_Angeles"}
        ),
        FamilyMember(
            name="Charlie Child",
            email="charlie@example.com",
            role="child",
            preferences={"timezone": "America/Los_Angeles", "school_schedule": True}
        ),
    ]

    for member in members:
        db_session.add(member)

    db_session.commit()

    for member in members:
        db_session.refresh(member)

    return members
