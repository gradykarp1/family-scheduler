"""
Unit tests for the resources service.

Tests resource availability checking functions.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.family import FamilyMember
from src.models.resources import Resource, ResourceReservation
from src.services.resources import (
    AvailabilitySlot,
    ResourceAvailability,
    check_resource_availability,
    check_multiple_resources,
    find_available_resources,
    get_resource_schedule,
    find_available_slots,
    get_resource_utilization,
    get_resources_by_type,
)


@pytest.fixture
def member(db_session):
    """Create a test family member."""
    member = FamilyMember(
        name="Test User",
        email="test@test.com",
        role="parent",
    )
    db_session.add(member)
    db_session.commit()
    return member


@pytest.fixture
def resources(db_session):
    """Create test resources."""
    car = Resource(
        name="Family Car",
        resource_type="vehicle",
        capacity=1,
        active=True,
    )
    van = Resource(
        name="Mini Van",
        resource_type="vehicle",
        capacity=1,
        active=True,
    )
    room = Resource(
        name="Conference Room",
        resource_type="room",
        capacity=10,  # Shared resource
        active=True,
    )
    inactive = Resource(
        name="Old Bike",
        resource_type="vehicle",
        capacity=1,
        active=False,
    )

    db_session.add_all([car, van, room, inactive])
    db_session.commit()
    return {"car": car, "van": van, "room": room, "inactive": inactive}


@pytest.fixture
def reservations(db_session, resources, member):
    """Create test reservations."""
    now = datetime.utcnow()

    car_res = ResourceReservation(
        resource_id=resources["car"].id,
        reserved_by=member.id,
        start_time=now + timedelta(days=1, hours=9),
        end_time=now + timedelta(days=1, hours=12),
        status="confirmed",
    )
    room_res1 = ResourceReservation(
        resource_id=resources["room"].id,
        reserved_by=member.id,
        start_time=now + timedelta(days=1, hours=10),
        end_time=now + timedelta(days=1, hours=11),
        quantity_reserved=3,
        status="confirmed",
    )
    room_res2 = ResourceReservation(
        resource_id=resources["room"].id,
        reserved_by=member.id,
        start_time=now + timedelta(days=1, hours=10),
        end_time=now + timedelta(days=1, hours=11),
        quantity_reserved=5,
        status="confirmed",
    )

    db_session.add_all([car_res, room_res1, room_res2])
    db_session.commit()
    return {"car_res": car_res, "room_res1": room_res1, "room_res2": room_res2}


class TestCheckResourceAvailability:
    """Test check_resource_availability function."""

    def test_available_resource(self, db_session, resources):
        """Test checking an available resource."""
        now = datetime.utcnow()

        result = check_resource_availability(
            db_session,
            resources["van"].id,
            now + timedelta(days=1, hours=9),
            now + timedelta(days=1, hours=10),
        )

        assert isinstance(result, ResourceAvailability)
        assert result.is_available is True
        assert result.resource_name == "Mini Van"
        assert result.total_capacity == 1

    def test_unavailable_resource(self, db_session, resources, reservations):
        """Test checking an unavailable resource."""
        now = datetime.utcnow()

        result = check_resource_availability(
            db_session,
            resources["car"].id,
            now + timedelta(days=1, hours=10),
            now + timedelta(days=1, hours=11),
        )

        assert result.is_available is False
        assert len(result.conflicting_reservations) >= 1

    def test_shared_resource_partial_availability(self, db_session, resources, reservations):
        """Test shared resource with partial capacity available."""
        now = datetime.utcnow()

        # Room has capacity 10, 8 seats reserved (3+5)
        result = check_resource_availability(
            db_session,
            resources["room"].id,
            now + timedelta(days=1, hours=10),
            now + timedelta(days=1, hours=11),
            quantity_needed=2,  # Need 2, have 2 available
        )

        assert result.is_available is True
        assert result.available_capacity == 2

    def test_shared_resource_insufficient_capacity(self, db_session, resources, reservations):
        """Test shared resource with insufficient capacity."""
        now = datetime.utcnow()

        result = check_resource_availability(
            db_session,
            resources["room"].id,
            now + timedelta(days=1, hours=10),
            now + timedelta(days=1, hours=11),
            quantity_needed=5,  # Need 5, only 2 available
        )

        assert result.is_available is False

    def test_inactive_resource(self, db_session, resources):
        """Test checking an inactive resource."""
        now = datetime.utcnow()

        result = check_resource_availability(
            db_session,
            resources["inactive"].id,
            now + timedelta(days=1),
            now + timedelta(days=1, hours=1),
        )

        assert result.is_available is False

    def test_nonexistent_resource(self, db_session):
        """Test checking a non-existent resource."""
        now = datetime.utcnow()

        result = check_resource_availability(
            db_session,
            uuid4(),
            now,
            now + timedelta(hours=1),
        )

        assert result.is_available is False
        assert result.total_capacity == 0

    def test_exclude_reservation(self, db_session, resources, reservations):
        """Test excluding a specific reservation from check."""
        now = datetime.utcnow()
        car_res = reservations["car_res"]

        result = check_resource_availability(
            db_session,
            resources["car"].id,
            car_res.start_time,
            car_res.end_time,
            exclude_reservation_id=car_res.id,
        )

        assert result.is_available is True


class TestCheckMultipleResources:
    """Test check_multiple_resources function."""

    def test_check_multiple(self, db_session, resources, reservations):
        """Test checking multiple resources at once."""
        now = datetime.utcnow()

        results = check_multiple_resources(
            db_session,
            [resources["car"].id, resources["van"].id],
            now + timedelta(days=1, hours=10),
            now + timedelta(days=1, hours=11),
        )

        assert len(results) == 2
        assert resources["car"].id in results
        assert resources["van"].id in results
        assert results[resources["car"].id].is_available is False
        assert results[resources["van"].id].is_available is True


class TestFindAvailableResources:
    """Test find_available_resources function."""

    def test_find_by_type(self, db_session, resources):
        """Test finding available resources by type."""
        result = find_available_resources(
            db_session,
            resource_type="vehicle",
        )

        # Should find car and van, not inactive
        names = {r.name for r in result}
        assert "Family Car" in names
        assert "Mini Van" in names
        assert "Old Bike" not in names

    def test_find_with_time_filter(self, db_session, resources, reservations):
        """Test finding resources available at a specific time."""
        now = datetime.utcnow()

        result = find_available_resources(
            db_session,
            resource_type="vehicle",
            start=now + timedelta(days=1, hours=10),
            end=now + timedelta(days=1, hours=11),
        )

        # Only van should be available (car is reserved)
        names = {r.name for r in result}
        assert "Mini Van" in names
        assert "Family Car" not in names

    def test_find_with_min_capacity(self, db_session, resources):
        """Test finding resources with minimum capacity."""
        result = find_available_resources(
            db_session,
            min_capacity=5,
        )

        # Only room has capacity >= 5
        assert len(result) == 1
        assert result[0].name == "Conference Room"


class TestGetResourceSchedule:
    """Test get_resource_schedule function."""

    def test_get_schedule(self, db_session, resources, reservations):
        """Test getting resource schedule."""
        now = datetime.utcnow()

        result = get_resource_schedule(
            db_session,
            resources["car"].id,
            now,
            now + timedelta(days=7),
        )

        assert len(result) >= 1
        assert all(r.resource_id == resources["car"].id for r in result)

    def test_empty_schedule(self, db_session, resources):
        """Test getting schedule for unreserved resource."""
        now = datetime.utcnow()

        result = get_resource_schedule(
            db_session,
            resources["van"].id,
            now,
            now + timedelta(days=7),
        )

        assert len(result) == 0


class TestFindAvailableSlots:
    """Test find_available_slots function."""

    def test_find_slots(self, db_session, resources):
        """Test finding available time slots."""
        tomorrow = datetime.utcnow() + timedelta(days=2)
        tomorrow = datetime(tomorrow.year, tomorrow.month, tomorrow.day)

        result = find_available_slots(
            db_session,
            resources["van"].id,
            tomorrow,
            duration=timedelta(hours=1),
            start_hour=9,
            end_hour=17,
            slot_interval=timedelta(hours=1),
        )

        assert len(result) > 0
        assert all(isinstance(s, AvailabilitySlot) for s in result)

    def test_slots_respect_reservations(self, db_session, resources, reservations):
        """Test that slots respect existing reservations."""
        car_res = reservations["car_res"]
        date = datetime(
            car_res.start_time.year,
            car_res.start_time.month,
            car_res.start_time.day,
        )

        result = find_available_slots(
            db_session,
            resources["car"].id,
            date,
            duration=timedelta(hours=1),
            start_hour=8,
            end_hour=14,
            slot_interval=timedelta(hours=1),
        )

        # No slots should overlap with the reservation
        for slot in result:
            # Slot should not be during reservation time
            overlaps = (
                slot.start < car_res.end_time and
                slot.end > car_res.start_time
            )
            assert not overlaps

    def test_inactive_resource_returns_empty(self, db_session, resources):
        """Test that inactive resource returns no slots."""
        tomorrow = datetime.utcnow() + timedelta(days=1)

        result = find_available_slots(
            db_session,
            resources["inactive"].id,
            tomorrow,
            duration=timedelta(hours=1),
        )

        assert len(result) == 0


class TestGetResourceUtilization:
    """Test get_resource_utilization function."""

    def test_utilization_calculation(self, db_session, resources, reservations):
        """Test calculating resource utilization."""
        car_res = reservations["car_res"]

        # Calculate utilization for a 24-hour period containing the reservation
        day_start = datetime(
            car_res.start_time.year,
            car_res.start_time.month,
            car_res.start_time.day,
            0, 0, 0,
        )
        day_end = day_start + timedelta(hours=24)

        utilization = get_resource_utilization(
            db_session,
            resources["car"].id,
            day_start,
            day_end,
        )

        # 3 hours reserved out of 24 = 12.5%
        assert 0.0 < utilization < 1.0
        expected = 3.0 / 24.0
        assert abs(utilization - expected) < 0.01

    def test_zero_utilization(self, db_session, resources):
        """Test utilization for unreserved resource."""
        now = datetime.utcnow()

        utilization = get_resource_utilization(
            db_session,
            resources["van"].id,
            now,
            now + timedelta(days=1),
        )

        assert utilization == 0.0

    def test_deleted_resource(self, db_session, resources):
        """Test utilization for deleted resource."""
        resources["car"].deleted_at = datetime.utcnow()
        db_session.commit()

        now = datetime.utcnow()
        utilization = get_resource_utilization(
            db_session,
            resources["car"].id,
            now,
            now + timedelta(days=1),
        )

        assert utilization == 0.0


class TestGetResourcesByType:
    """Test get_resources_by_type function."""

    def test_get_vehicles(self, db_session, resources):
        """Test getting all vehicle resources."""
        result = get_resources_by_type(db_session, "vehicle")

        # Should get car and van, not inactive
        names = {r.name for r in result}
        assert "Family Car" in names
        assert "Mini Van" in names
        assert "Old Bike" not in names

    def test_get_rooms(self, db_session, resources):
        """Test getting all room resources."""
        result = get_resources_by_type(db_session, "room")

        assert len(result) == 1
        assert result[0].name == "Conference Room"

    def test_include_inactive(self, db_session, resources):
        """Test including inactive resources."""
        result = get_resources_by_type(db_session, "vehicle", active_only=False)

        names = {r.name for r in result}
        assert "Old Bike" in names

    def test_nonexistent_type(self, db_session, resources):
        """Test getting resources of non-existent type."""
        result = get_resources_by_type(db_session, "spaceship")
        assert len(result) == 0
