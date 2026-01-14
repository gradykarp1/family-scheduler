"""
Unit tests for the queries service.

Tests family configuration query functions for:
- Family members
- Calendars
- Resources
- Constraints

Note: Events are stored in Google Calendar, not the local database.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.models.family import FamilyMember, Calendar
from src.models.resources import Resource
from src.models.constraints import Constraint
from src.services.queries import (
    get_all_family_members,
    get_family_member_by_id,
    get_family_member_by_email,
    get_family_members_by_role,
    get_all_calendars,
    get_calendars_by_owner,
    get_calendar_by_id,
    get_calendar_by_google_id,
    get_calendars_by_type,
    get_all_resources,
    get_resource_by_id,
    get_resources_by_type,
    get_all_constraints,
    get_constraints_for_member,
    get_constraints_by_type,
)


@pytest.fixture
def members(db_session):
    """Create test family members."""
    mom = FamilyMember(
        name="Mom",
        email="mom@test.com",
        role="parent",
        preferences={"timezone": "America/Los_Angeles"}
    )
    dad = FamilyMember(
        name="Dad",
        email="dad@test.com",
        role="parent",
        preferences={"timezone": "America/Los_Angeles"}
    )
    kid = FamilyMember(
        name="Kid",
        email="kid@test.com",
        role="child",
        preferences={"timezone": "America/Los_Angeles"}
    )
    db_session.add_all([mom, dad, kid])
    db_session.commit()
    return {"mom": mom, "dad": dad, "kid": kid}


@pytest.fixture
def calendars(db_session, members):
    """Create test calendars."""
    family_cal = Calendar(
        name="Family Calendar",
        calendar_type="family",
        google_calendar_id="family@group.calendar.google.com",
        visibility="family"
    )
    mom_cal = Calendar(
        name="Mom's Calendar",
        calendar_type="personal",
        google_calendar_id="mom@calendar.google.com",
        owner_id=members["mom"].id,
        visibility="private"
    )
    dad_cal = Calendar(
        name="Dad's Calendar",
        calendar_type="personal",
        google_calendar_id="dad@calendar.google.com",
        owner_id=members["dad"].id,
        visibility="private"
    )
    db_session.add_all([family_cal, mom_cal, dad_cal])
    db_session.commit()
    return {"family": family_cal, "mom": mom_cal, "dad": dad_cal}


@pytest.fixture
def resources(db_session):
    """Create test resources."""
    car = Resource(
        name="Family Car",
        resource_type="vehicle",
        capacity=1,
        active=True,
        resource_metadata={"color": "blue"}
    )
    room = Resource(
        name="Conference Room",
        resource_type="room",
        capacity=10,
        active=True,
        google_calendar_id="room@resource.calendar.google.com",
        resource_metadata={"has_projector": True}
    )
    inactive = Resource(
        name="Old Laptop",
        resource_type="equipment",
        capacity=1,
        active=False,
        resource_metadata={}
    )
    db_session.add_all([car, room, inactive])
    db_session.commit()
    return {"car": car, "room": room, "inactive": inactive}


@pytest.fixture
def constraints(db_session, members):
    """Create test constraints."""
    work_hours = Constraint(
        name="Work Hours",
        description="No events during work hours",
        family_member_id=members["mom"].id,
        constraint_type="availability",
        level="hard",
        priority=10,
        rule={"type": "time_window", "start": "09:00", "end": "17:00"},
        active=True
    )
    school = Constraint(
        name="School Hours",
        description="Kid is at school",
        family_member_id=members["kid"].id,
        constraint_type="availability",
        level="hard",
        priority=8,
        rule={"type": "time_window", "start": "08:00", "end": "15:00"},
        active=True
    )
    inactive_constraint = Constraint(
        name="Old Constraint",
        description="No longer applies",
        family_member_id=members["dad"].id,
        constraint_type="preference",
        level="soft",
        priority=1,
        rule={},
        active=False
    )
    db_session.add_all([work_hours, school, inactive_constraint])
    db_session.commit()
    return {"work_hours": work_hours, "school": school, "inactive": inactive_constraint}


class TestFamilyMemberQueries:
    """Test family member query functions."""

    def test_get_all_family_members(self, db_session, members):
        """Test getting all family members."""
        result = get_all_family_members(db_session)

        assert len(result) == 3
        names = {m.name for m in result}
        assert names == {"Mom", "Dad", "Kid"}

    def test_get_all_family_members_excludes_deleted(self, db_session, members):
        """Test that soft-deleted members are excluded by default."""
        members["kid"].deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        result = get_all_family_members(db_session)

        assert len(result) == 2
        names = {m.name for m in result}
        assert "Kid" not in names

    def test_get_all_family_members_include_deleted(self, db_session, members):
        """Test including soft-deleted members."""
        members["kid"].deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        result = get_all_family_members(db_session, include_deleted=True)

        assert len(result) == 3

    def test_get_family_member_by_id(self, db_session, members):
        """Test getting a member by ID."""
        result = get_family_member_by_id(db_session, members["mom"].id)

        assert result is not None
        assert result.name == "Mom"
        assert result.email == "mom@test.com"

    def test_get_family_member_by_id_not_found(self, db_session):
        """Test getting a non-existent member."""
        result = get_family_member_by_id(db_session, uuid4())
        assert result is None

    def test_get_family_member_by_email(self, db_session, members):
        """Test getting a member by email."""
        result = get_family_member_by_email(db_session, "dad@test.com")

        assert result is not None
        assert result.name == "Dad"

    def test_get_family_member_by_email_not_found(self, db_session, members):
        """Test getting a member by non-existent email."""
        result = get_family_member_by_email(db_session, "unknown@test.com")
        assert result is None

    def test_get_family_members_by_role(self, db_session, members):
        """Test getting members by role."""
        parents = get_family_members_by_role(db_session, "parent")
        children = get_family_members_by_role(db_session, "child")

        assert len(parents) == 2
        assert len(children) == 1
        assert children[0].name == "Kid"


class TestCalendarQueries:
    """Test calendar query functions."""

    def test_get_all_calendars(self, db_session, calendars):
        """Test getting all calendars."""
        result = get_all_calendars(db_session)

        assert len(result) == 3
        names = {c.name for c in result}
        assert "Family Calendar" in names

    def test_get_calendars_by_owner(self, db_session, members, calendars):
        """Test getting calendars by owner."""
        result = get_calendars_by_owner(db_session, members["mom"].id)

        assert len(result) == 1
        assert result[0].name == "Mom's Calendar"

    def test_get_calendar_by_id(self, db_session, calendars):
        """Test getting a calendar by ID."""
        result = get_calendar_by_id(db_session, calendars["family"].id)

        assert result is not None
        assert result.name == "Family Calendar"

    def test_get_calendar_by_id_not_found(self, db_session):
        """Test getting a non-existent calendar."""
        result = get_calendar_by_id(db_session, uuid4())
        assert result is None

    def test_get_calendar_by_google_id(self, db_session, calendars):
        """Test getting a calendar by Google Calendar ID."""
        result = get_calendar_by_google_id(
            db_session, "mom@calendar.google.com"
        )

        assert result is not None
        assert result.name == "Mom's Calendar"

    def test_get_calendar_by_google_id_not_found(self, db_session, calendars):
        """Test getting a calendar by non-existent Google ID."""
        result = get_calendar_by_google_id(db_session, "unknown@calendar.google.com")
        assert result is None

    def test_get_calendars_by_type(self, db_session, calendars):
        """Test getting calendars by type."""
        personal = get_calendars_by_type(db_session, "personal")
        family = get_calendars_by_type(db_session, "family")

        assert len(personal) == 2
        assert len(family) == 1


class TestResourceQueries:
    """Test resource query functions."""

    def test_get_all_resources_active_only(self, db_session, resources):
        """Test getting only active resources."""
        result = get_all_resources(db_session, active_only=True)

        assert len(result) == 2
        names = {r.name for r in result}
        assert "Old Laptop" not in names

    def test_get_all_resources_include_inactive(self, db_session, resources):
        """Test getting all resources including inactive."""
        result = get_all_resources(db_session, active_only=False)

        assert len(result) == 3

    def test_get_resource_by_id(self, db_session, resources):
        """Test getting a resource by ID."""
        result = get_resource_by_id(db_session, resources["car"].id)

        assert result is not None
        assert result.name == "Family Car"

    def test_get_resource_by_id_not_found(self, db_session):
        """Test getting a non-existent resource."""
        result = get_resource_by_id(db_session, uuid4())
        assert result is None

    def test_get_resources_by_type(self, db_session, resources):
        """Test getting resources by type."""
        vehicles = get_resources_by_type(db_session, "vehicle")
        rooms = get_resources_by_type(db_session, "room")
        equipment = get_resources_by_type(db_session, "equipment", active_only=False)

        assert len(vehicles) == 1
        assert len(rooms) == 1
        assert len(equipment) == 1


class TestConstraintQueries:
    """Test constraint query functions."""

    def test_get_all_constraints_active_only(self, db_session, constraints):
        """Test getting only active constraints."""
        result = get_all_constraints(db_session, active_only=True)

        assert len(result) == 2
        names = {c.name for c in result}
        assert "Old Constraint" not in names

    def test_get_all_constraints_include_inactive(self, db_session, constraints):
        """Test getting all constraints including inactive."""
        result = get_all_constraints(db_session, active_only=False)

        assert len(result) == 3

    def test_constraints_ordered_by_priority(self, db_session, constraints):
        """Test that constraints are ordered by priority (descending)."""
        result = get_all_constraints(db_session, active_only=True)

        # Higher priority first
        assert result[0].priority >= result[1].priority

    def test_get_constraints_for_member(self, db_session, members, constraints):
        """Test getting constraints for a specific member."""
        result = get_constraints_for_member(db_session, members["mom"].id)

        assert len(result) == 1
        assert result[0].name == "Work Hours"

    def test_get_constraints_for_member_no_constraints(self, db_session, members, constraints):
        """Test getting constraints for member with no active constraints."""
        result = get_constraints_for_member(db_session, members["dad"].id)

        # Dad only has an inactive constraint
        assert len(result) == 0

    def test_get_constraints_by_type(self, db_session, constraints):
        """Test getting constraints by type."""
        availability = get_constraints_by_type(db_session, "availability")
        preference = get_constraints_by_type(db_session, "preference", active_only=False)

        assert len(availability) == 2
        assert len(preference) == 1
