"""
Pytest configuration and fixtures for Family Scheduler tests.

Provides database session fixtures and sample data for testing.
Note: Events are stored in Google Calendar, not the local database.
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
from src.models.resources import Resource
from src.models.constraints import Constraint


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
        Calendar: A persisted calendar with Google Calendar ID
    """
    calendar = Calendar(
        name="Family Calendar",
        description="Main family calendar",
        calendar_type="family",
        google_calendar_id="family@group.calendar.google.com",
        color="#FF5733",
        owner_id=sample_family_member.id,
        visibility="family"
    )
    db_session.add(calendar)
    db_session.commit()
    db_session.refresh(calendar)
    return calendar


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
def sample_resource_with_calendar(db_session: Session) -> Resource:
    """
    Create a sample Resource with a Google Calendar for availability tracking.

    Returns:
        Resource: A persisted resource with google_calendar_id
    """
    resource = Resource(
        name="Conference Room",
        description="Main meeting room",
        resource_type="room",
        capacity=10,
        location="2nd Floor",
        active=True,
        google_calendar_id="conference.room@resource.calendar.google.com",
        resource_metadata={
            "has_projector": True,
            "has_whiteboard": True
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


@pytest.fixture
def multiple_calendars(db_session: Session, multiple_family_members: list[FamilyMember]) -> list[Calendar]:
    """
    Create multiple calendars for testing.

    Returns:
        list[Calendar]: List of persisted calendars with Google Calendar IDs
    """
    calendars = [
        Calendar(
            name="Family Calendar",
            description="Shared family calendar",
            calendar_type="family",
            google_calendar_id="family@group.calendar.google.com",
            visibility="family"
        ),
        Calendar(
            name="Alice's Calendar",
            description="Alice's personal calendar",
            calendar_type="personal",
            google_calendar_id="alice@calendar.google.com",
            owner_id=multiple_family_members[0].id,
            visibility="private"
        ),
        Calendar(
            name="Bob's Calendar",
            description="Bob's personal calendar",
            calendar_type="personal",
            google_calendar_id="bob@calendar.google.com",
            owner_id=multiple_family_members[1].id,
            visibility="private"
        ),
    ]

    for calendar in calendars:
        db_session.add(calendar)

    db_session.commit()

    for calendar in calendars:
        db_session.refresh(calendar)

    return calendars


@pytest.fixture
def multiple_resources(db_session: Session) -> list[Resource]:
    """
    Create multiple resources for testing.

    Returns:
        list[Resource]: List of persisted resources
    """
    resources = [
        Resource(
            name="Family Car",
            description="Honda Accord",
            resource_type="vehicle",
            capacity=1,
            location="Garage",
            active=True,
            resource_metadata={"color": "blue", "seats": 5}
        ),
        Resource(
            name="Kitchen",
            description="Main kitchen",
            resource_type="room",
            capacity=4,
            location="First Floor",
            active=True,
            resource_metadata={"has_stove": True}
        ),
        Resource(
            name="Shared Laptop",
            description="Family laptop for homework",
            resource_type="equipment",
            capacity=1,
            location="Living Room",
            active=True,
            resource_metadata={"brand": "Dell"}
        ),
    ]

    for resource in resources:
        db_session.add(resource)

    db_session.commit()

    for resource in resources:
        db_session.refresh(resource)

    return resources
