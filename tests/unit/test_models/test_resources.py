"""
Unit tests for Resource and ResourceReservation models.

Tests:
- Resource creation and types
- Capacity model (exclusive vs shared resources)
- ResourceReservation creation and relationships
- Time-range reservations
- Reservation status workflow
- Quantity reserved vs available capacity
- Resource metadata JSON field
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.orm import Session

from src.models.resources import Resource, ResourceReservation
from src.models.family import FamilyMember
from src.models.events import Event
from src.models.family import Calendar


class TestResource:
    """Test Resource model functionality."""

    def test_create_resource(self, db_session: Session):
        """Test creating a basic resource."""
        resource = Resource(
            name="Family Car",
            description="Honda Accord 2020",
            resource_type="vehicle",
            capacity=1,
            location="Garage",
            active=True,
            resource_metadata={
                "color": "blue",
                "license_plate": "ABC123",
                "seats": 5
            }
        )
        db_session.add(resource)
        db_session.commit()
        db_session.refresh(resource)

        assert resource.id is not None
        assert resource.name == "Family Car"
        assert resource.description == "Honda Accord 2020"
        assert resource.resource_type == "vehicle"
        assert resource.capacity == 1
        assert resource.location == "Garage"
        assert resource.active is True
        assert resource.resource_metadata["color"] == "blue"
        assert resource.created_at is not None
        assert resource.deleted_at is None

    def test_resource_types(self, db_session: Session):
        """Test different resource types."""
        resource_types = ["vehicle", "room", "equipment", "other"]

        for res_type in resource_types:
            resource = Resource(
                name=f"Test {res_type.title()}",
                resource_type=res_type,
                capacity=1,
                active=True,
                resource_metadata={}
            )
            db_session.add(resource)

        db_session.commit()

        resources = db_session.query(Resource).all()
        saved_types = {r.resource_type for r in resources}
        assert saved_types == set(resource_types)

    def test_resource_exclusive_capacity(self, db_session: Session):
        """Test resource with capacity=1 (exclusive use)."""
        resource = Resource(
            name="Conference Room",
            resource_type="room",
            capacity=1,  # Only one group can use at a time
            active=True,
            resource_metadata={"seats": 12}
        )
        db_session.add(resource)
        db_session.commit()

        assert resource.capacity == 1

    def test_resource_shared_capacity(self, db_session: Session):
        """Test resource with capacity>1 (shared use)."""
        resource = Resource(
            name="Shared Laptop Pool",
            resource_type="equipment",
            capacity=5,  # Up to 5 people can borrow laptops simultaneously
            active=True,
            resource_metadata={"available_laptops": 5}
        )
        db_session.add(resource)
        db_session.commit()

        assert resource.capacity == 5

    def test_resource_active_inactive(self, db_session: Session):
        """Test active and inactive resources."""
        active_resource = Resource(
            name="Active Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        inactive_resource = Resource(
            name="Inactive Resource",
            resource_type="equipment",
            capacity=1,
            active=False,
            resource_metadata={}
        )

        db_session.add_all([active_resource, inactive_resource])
        db_session.commit()

        # Query only active resources
        active_resources = db_session.query(Resource).filter_by(active=True).all()
        assert len(active_resources) == 1
        assert active_resources[0].name == "Active Resource"

    def test_resource_location_field(self, db_session: Session):
        """Test resource location tracking."""
        resources = [
            Resource(
                name="Garage Tools",
                resource_type="equipment",
                capacity=1,
                location="Garage",
                active=True,
                resource_metadata={}
            ),
            Resource(
                name="Kitchen Appliance",
                resource_type="equipment",
                capacity=1,
                location="Kitchen",
                active=True,
                resource_metadata={}
            ),
        ]

        db_session.add_all(resources)
        db_session.commit()

        # Query by location
        garage_resources = db_session.query(Resource).filter_by(location="Garage").all()
        assert len(garage_resources) == 1
        assert garage_resources[0].name == "Garage Tools"

    def test_resource_metadata_json(self, db_session: Session):
        """Test storing complex metadata in JSON field."""
        metadata = {
            "make": "Honda",
            "model": "Accord",
            "year": 2020,
            "features": ["bluetooth", "backup camera", "cruise control"],
            "maintenance": {
                "last_oil_change": "2026-01-15",
                "next_service": "2026-07-15"
            }
        }

        resource = Resource(
            name="Honda Accord",
            resource_type="vehicle",
            capacity=1,
            active=True,
            resource_metadata=metadata
        )
        db_session.add(resource)
        db_session.commit()
        db_session.refresh(resource)

        # Verify nested structure preserved
        assert resource.resource_metadata["make"] == "Honda"
        assert len(resource.resource_metadata["features"]) == 3
        assert resource.resource_metadata["maintenance"]["last_oil_change"] == "2026-01-15"

    def test_resource_soft_delete(self, db_session: Session):
        """Test soft deletion of resource."""
        resource = Resource(
            name="To Delete",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add(resource)
        db_session.commit()
        resource_id = resource.id

        # Soft delete
        resource.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_resource = db_session.query(Resource).filter_by(id=resource_id).first()
        assert deleted_resource is not None
        assert deleted_resource.deleted_at is not None

    def test_resource_repr(self, db_session: Session):
        """Test string representation."""
        resource = Resource(
            name="Family Car",
            resource_type="vehicle",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add(resource)
        db_session.commit()

        repr_str = repr(resource)
        assert "Resource" in repr_str
        assert "Family Car" in repr_str
        assert "vehicle" in repr_str
        assert "capacity=1" in repr_str


class TestResourceReservation:
    """Test ResourceReservation model functionality."""

    def test_create_reservation(self, db_session: Session):
        """Test creating a basic reservation."""
        member = FamilyMember(name="Reserver", role="parent", preferences={})
        resource = Resource(
            name="Family Car",
            resource_type="vehicle",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="proposed",
            notes="Need for grocery shopping"
        )
        db_session.add(reservation)
        db_session.commit()
        db_session.refresh(reservation)

        assert reservation.id is not None
        assert reservation.resource_id == resource.id
        assert reservation.reserved_by == member.id
        assert reservation.quantity_reserved == 1
        assert reservation.status == "proposed"
        assert reservation.notes == "Need for grocery shopping"
        assert reservation.created_at is not None
        assert reservation.deleted_at is None

    def test_reservation_linked_to_event(self, db_session: Session):
        """Test reservation linked to an event."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        resource = Resource(
            name="Conference Room",
            resource_type="room",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, calendar, resource])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Team Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            event_id=event.id,
            reserved_by=member.id,
            start_time=event.start_time,
            end_time=event.end_time,
            quantity_reserved=1,
            status="confirmed"
        )
        db_session.add(reservation)
        db_session.commit()
        db_session.refresh(reservation)

        # Verify relationships
        assert reservation.event_id == event.id
        assert reservation.event.title == "Team Meeting"
        assert reservation.resource.name == "Conference Room"

    def test_reservation_standalone_no_event(self, db_session: Session):
        """Test standalone reservation (not linked to event)."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Tools",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            event_id=None,  # No event linkage
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="confirmed",
            notes="Maintenance block"
        )
        db_session.add(reservation)
        db_session.commit()

        assert reservation.event_id is None
        assert reservation.event is None

    def test_reservation_status_values(self, db_session: Session):
        """Test different reservation status values."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Resource",
            resource_type="equipment",
            capacity=3,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        statuses = ["proposed", "confirmed", "cancelled"]

        for i, status in enumerate(statuses):
            reservation = ResourceReservation(
                resource_id=resource.id,
                reserved_by=member.id,
                start_time=datetime(2026, 2, 15, 10+i, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 11+i, 0, tzinfo=timezone.utc),
                quantity_reserved=1,
                status=status
            )
            db_session.add(reservation)

        db_session.commit()

        reservations = db_session.query(ResourceReservation).all()
        saved_statuses = {r.status for r in reservations}
        assert saved_statuses == set(statuses)

    def test_reservation_quantity_for_shared_resource(self, db_session: Session):
        """Test reserving different quantities from shared resource."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Laptop Pool",
            resource_type="equipment",
            capacity=5,  # 5 laptops available
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        # Reserve 2 laptops
        reservation = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=2,  # Taking 2 out of 5
            status="confirmed"
        )
        db_session.add(reservation)
        db_session.commit()

        assert reservation.quantity_reserved == 2
        # 3 laptops should still be available (capacity - quantity_reserved)

    def test_reservation_time_range_overlap_detection(self, db_session: Session):
        """Test detecting overlapping reservations."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Conference Room",
            resource_type="room",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        # Create first reservation
        res1 = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="confirmed"
        )
        db_session.add(res1)
        db_session.commit()

        # Try to create overlapping reservation
        res2 = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),  # Overlaps!
            end_time=datetime(2026, 2, 15, 13, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="proposed"
        )
        db_session.add(res2)
        db_session.commit()

        # Query overlapping reservations
        overlapping = db_session.query(ResourceReservation).filter(
            ResourceReservation.resource_id == resource.id,
            ResourceReservation.status == "confirmed",
            ResourceReservation.start_time < res2.end_time,
            ResourceReservation.end_time > res2.start_time
        ).all()

        assert len(overlapping) >= 1
        assert res1 in overlapping

    def test_reservation_reserver_relationship(self, db_session: Session):
        """Test reservation-reserver relationship."""
        member = FamilyMember(name="Reserver", role="parent", preferences={})
        resource = Resource(
            name="Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="confirmed"
        )
        db_session.add(reservation)
        db_session.commit()
        db_session.refresh(reservation)

        # Verify relationship
        assert reservation.reserver is not None
        assert reservation.reserver.name == "Reserver"

    def test_resource_reservations_relationship(self, db_session: Session):
        """Test accessing all reservations for a resource."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Popular Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        # Create multiple reservations
        for i in range(3):
            reservation = ResourceReservation(
                resource_id=resource.id,
                reserved_by=member.id,
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 12, 0, tzinfo=timezone.utc),
                quantity_reserved=1,
                status="confirmed"
            )
            db_session.add(reservation)

        db_session.commit()
        db_session.refresh(resource)

        # Verify resource has 3 reservations
        assert len(resource.reservations) == 3

    def test_query_reservations_by_date_range(self, db_session: Session):
        """Test querying reservations by date range."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        # Create reservations on different dates
        reservations = [
            ResourceReservation(
                resource_id=resource.id,
                reserved_by=member.id,
                start_time=datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc),
                quantity_reserved=1,
                status="confirmed"
            ),
            ResourceReservation(
                resource_id=resource.id,
                reserved_by=member.id,
                start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
                quantity_reserved=1,
                status="confirmed"
            ),
            ResourceReservation(
                resource_id=resource.id,
                reserved_by=member.id,
                start_time=datetime(2026, 2, 20, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc),
                quantity_reserved=1,
                status="confirmed"
            ),
        ]
        db_session.add_all(reservations)
        db_session.commit()

        # Query reservations in date range
        range_start = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
        range_end = datetime(2026, 2, 18, 23, 59, tzinfo=timezone.utc)

        in_range = db_session.query(ResourceReservation).filter(
            ResourceReservation.start_time >= range_start,
            ResourceReservation.end_time <= range_end
        ).all()

        assert len(in_range) == 1
        assert in_range[0].start_time.day == 15

    def test_reservation_soft_delete(self, db_session: Session):
        """Test soft deletion of reservation."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="confirmed"
        )
        db_session.add(reservation)
        db_session.commit()
        reservation_id = reservation.id

        # Soft delete
        reservation.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_res = db_session.query(ResourceReservation).filter_by(id=reservation_id).first()
        assert deleted_res is not None
        assert deleted_res.deleted_at is not None

    def test_reservation_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        resource = Resource(
            name="Resource",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add_all([member, resource])
        db_session.commit()

        reservation = ResourceReservation(
            resource_id=resource.id,
            reserved_by=member.id,
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc),
            quantity_reserved=1,
            status="confirmed"
        )
        db_session.add(reservation)
        db_session.commit()

        repr_str = repr(reservation)
        assert "ResourceReservation" in repr_str
        assert str(resource.id) in repr_str
        assert "confirmed" in repr_str
