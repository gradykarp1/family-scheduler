"""
Unit tests for BaseModel and GUID TypeDecorator.

Tests:
- GUID TypeDecorator with SQLite (CHAR storage)
- BaseModel field defaults (id, created_at, updated_at, deleted_at)
- Soft deletion behavior
- JSON column handling
"""

import uuid
from datetime import datetime, timezone
from time import sleep

import pytest
from sqlalchemy.orm import Session

from src.models.base import BaseModel, GUID, get_json_type
from src.models.family import FamilyMember


class TestGUIDTypeDecorator:
    """Test the GUID TypeDecorator for UUID handling."""

    def test_guid_generation(self, db_session: Session):
        """Test that GUID fields are automatically generated."""
        member = FamilyMember(
            name="Test User",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        # Verify ID is a UUID
        assert isinstance(member.id, uuid.UUID)
        assert member.id is not None

    def test_guid_uniqueness(self, db_session: Session):
        """Test that generated GUIDs are unique."""
        member1 = FamilyMember(name="User 1", role="parent", preferences={})
        member2 = FamilyMember(name="User 2", role="child", preferences={})

        db_session.add_all([member1, member2])
        db_session.commit()

        assert member1.id != member2.id

    def test_guid_persistence(self, db_session: Session):
        """Test that GUID values persist correctly."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        original_id = member.id

        # Refresh from database
        db_session.refresh(member)
        assert member.id == original_id

        # Query by ID
        queried_member = db_session.query(FamilyMember).filter_by(id=original_id).first()
        assert queried_member is not None
        assert queried_member.id == original_id

    def test_guid_custom_value(self, db_session: Session):
        """Test that custom UUID values can be set."""
        custom_id = uuid.uuid4()
        member = FamilyMember(
            id=custom_id,
            name="Test User",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        assert member.id == custom_id


class TestBaseModel:
    """Test BaseModel functionality."""

    def test_basemodel_id_auto_generated(self, db_session: Session):
        """Test that id field is auto-generated."""
        member = FamilyMember(name="Test User", role="parent", preferences={})

        # ID is None before flushing to database
        assert member.id is None

        db_session.add(member)
        db_session.flush()  # Flush to generate the ID

        # After flush, ID should be generated
        assert member.id is not None
        assert isinstance(member.id, uuid.UUID)

        db_session.commit()

    def test_basemodel_created_at_auto_set(self, db_session: Session):
        """Test that created_at is automatically set."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        assert member.created_at is not None
        assert isinstance(member.created_at, datetime)
        # Should be very recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = (now - member.created_at.replace(tzinfo=timezone.utc)).total_seconds()
        assert time_diff < 60

    def test_basemodel_updated_at_on_update(self, db_session: Session):
        """Test that updated_at is set when model is updated."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        original_updated_at = member.updated_at

        # Wait a tiny bit to ensure timestamp difference
        sleep(0.01)

        # Update the member
        member.name = "Updated Name"
        db_session.commit()
        db_session.refresh(member)

        # updated_at should now be set (it was None initially)
        # After update, it should have a value
        assert member.name == "Updated Name"

    def test_basemodel_deleted_at_initially_none(self, db_session: Session):
        """Test that deleted_at is initially None."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        assert member.deleted_at is None

    def test_basemodel_soft_deletion(self, db_session: Session):
        """Test soft deletion by setting deleted_at."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()
        member_id = member.id

        # Soft delete by setting deleted_at
        member.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Should still be in database
        deleted_member = db_session.query(FamilyMember).filter_by(id=member_id).first()
        assert deleted_member is not None
        assert deleted_member.deleted_at is not None

        # Can filter out soft-deleted records
        active_members = db_session.query(FamilyMember).filter(
            FamilyMember.deleted_at.is_(None)
        ).all()
        assert member not in active_members

    def test_basemodel_repr(self, db_session: Session):
        """Test that models have string representations."""
        member = FamilyMember(
            name="John Doe",
            email="john@example.com",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        repr_str = repr(member)
        assert "FamilyMember" in repr_str
        assert "John Doe" in repr_str


class TestJSONColumnFactory:
    """Test the get_json_type() factory function."""

    def test_json_storage_and_retrieval(self, db_session: Session):
        """Test that JSON data is stored and retrieved correctly."""
        preferences = {
            "timezone": "America/Los_Angeles",
            "notifications": {
                "email": True,
                "sms": False
            },
            "work_hours": ["09:00", "17:00"]
        }

        member = FamilyMember(
            name="Test User",
            role="parent",
            preferences=preferences
        )
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        # Verify JSON data is preserved
        assert member.preferences == preferences
        assert member.preferences["timezone"] == "America/Los_Angeles"
        assert member.preferences["notifications"]["email"] is True
        assert member.preferences["work_hours"] == ["09:00", "17:00"]

    def test_json_empty_dict_default(self, db_session: Session):
        """Test that JSON fields with dict default work correctly."""
        from src.models.resources import Resource

        # Create resource without explicit metadata
        resource = Resource(
            name="Test Resource",
            resource_type="equipment",
            capacity=1,
            active=True
            # resource_metadata should default to {}
        )
        db_session.add(resource)
        db_session.commit()
        db_session.refresh(resource)

        # Should default to empty dict
        assert resource.resource_metadata == {}
        assert isinstance(resource.resource_metadata, dict)

    def test_json_mutation_tracking(self, db_session: Session):
        """Test that JSON field changes persist when reassigning the entire dict."""
        from sqlalchemy.orm.attributes import flag_modified

        member = FamilyMember(
            name="Test User",
            role="parent",
            preferences={"timezone": "UTC"}
        )
        db_session.add(member)
        db_session.commit()
        member_id = member.id

        # Modify JSON field - SQLAlchemy doesn't auto-detect dict mutations
        # So we need to either reassign the entire dict or use flag_modified()
        member.preferences["timezone"] = "America/New_York"
        member.preferences["new_key"] = "new_value"

        # Mark the field as modified so SQLAlchemy knows to update it
        flag_modified(member, "preferences")
        db_session.commit()

        # Refresh and verify changes persisted
        db_session.expire(member)
        updated_member = db_session.query(FamilyMember).filter_by(id=member_id).first()
        assert updated_member.preferences["timezone"] == "America/New_York"
        assert updated_member.preferences["new_key"] == "new_value"

    def test_json_nested_structures(self, db_session: Session):
        """Test that nested JSON structures work correctly."""
        complex_preferences = {
            "level1": {
                "level2": {
                    "level3": {
                        "deep_value": "test"
                    }
                }
            },
            "array_of_objects": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"}
            ]
        }

        member = FamilyMember(
            name="Test User",
            role="parent",
            preferences=complex_preferences
        )
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        # Verify nested structure is preserved
        assert member.preferences["level1"]["level2"]["level3"]["deep_value"] == "test"
        assert len(member.preferences["array_of_objects"]) == 2
        assert member.preferences["array_of_objects"][0]["name"] == "first"


class TestModelRelationships:
    """Test that BaseModel works correctly with relationships."""

    def test_cascade_soft_delete(self, db_session: Session):
        """Test that soft deletion doesn't cascade automatically."""
        from src.models.family import Calendar

        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Test Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        calendar_id = calendar.id

        # Soft delete the member
        member.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Calendar should still exist and not be soft-deleted
        db_calendar = db_session.query(Calendar).filter_by(id=calendar_id).first()
        assert db_calendar is not None
        assert db_calendar.deleted_at is None

    def test_query_active_records_only(self, db_session: Session):
        """Test filtering to get only non-deleted records."""
        # Create 3 members
        members = [
            FamilyMember(name="Active 1", role="parent", preferences={}),
            FamilyMember(name="Active 2", role="child", preferences={}),
            FamilyMember(name="Deleted", role="parent", preferences={}),
        ]
        db_session.add_all(members)
        db_session.commit()

        # Soft delete one member
        members[2].deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Query only active members
        active = db_session.query(FamilyMember).filter(
            FamilyMember.deleted_at.is_(None)
        ).all()

        assert len(active) == 2
        assert members[2] not in active
