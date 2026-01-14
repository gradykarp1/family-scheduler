"""
Unit tests for Resource model.

Tests:
- Resource creation and types
- Capacity model (exclusive vs shared resources)
- Google Calendar ID for availability tracking
- Resource metadata JSON field
- Soft deletion
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from src.models.resources import Resource


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

    def test_resource_with_google_calendar(self, db_session: Session):
        """Test resource with Google Calendar for availability tracking."""
        resource = Resource(
            name="Conference Room A",
            resource_type="room",
            capacity=10,
            location="2nd Floor",
            active=True,
            google_calendar_id="conference.a@resource.calendar.google.com",
            resource_metadata={"has_projector": True}
        )
        db_session.add(resource)
        db_session.commit()
        db_session.refresh(resource)

        assert resource.google_calendar_id == "conference.a@resource.calendar.google.com"

    def test_resource_without_google_calendar(self, db_session: Session):
        """Test resource without Google Calendar (no availability tracking)."""
        resource = Resource(
            name="Hand Tools",
            resource_type="equipment",
            capacity=1,
            active=True,
            resource_metadata={}
        )
        db_session.add(resource)
        db_session.commit()
        db_session.refresh(resource)

        assert resource.google_calendar_id is None

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

    def test_query_resources_by_type(self, db_session: Session):
        """Test querying resources by type."""
        resources = [
            Resource(name="Car 1", resource_type="vehicle", capacity=1, active=True, resource_metadata={}),
            Resource(name="Car 2", resource_type="vehicle", capacity=1, active=True, resource_metadata={}),
            Resource(name="Room 1", resource_type="room", capacity=1, active=True, resource_metadata={}),
        ]
        db_session.add_all(resources)
        db_session.commit()

        vehicles = db_session.query(Resource).filter_by(resource_type="vehicle").all()
        assert len(vehicles) == 2

        rooms = db_session.query(Resource).filter_by(resource_type="room").all()
        assert len(rooms) == 1

    def test_query_resources_with_calendar(self, db_session: Session):
        """Test querying resources that have Google Calendar tracking."""
        resources = [
            Resource(
                name="Room A",
                resource_type="room",
                capacity=1,
                active=True,
                google_calendar_id="room.a@resource.calendar.google.com",
                resource_metadata={}
            ),
            Resource(
                name="Room B",
                resource_type="room",
                capacity=1,
                active=True,
                google_calendar_id=None,  # No calendar tracking
                resource_metadata={}
            ),
        ]
        db_session.add_all(resources)
        db_session.commit()

        # Query resources with calendar
        with_calendar = db_session.query(Resource).filter(
            Resource.google_calendar_id.isnot(None)
        ).all()
        assert len(with_calendar) == 1
        assert with_calendar[0].name == "Room A"
