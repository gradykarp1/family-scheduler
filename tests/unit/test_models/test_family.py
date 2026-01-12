"""
Unit tests for FamilyMember and Calendar models.

Tests:
- FamilyMember creation and field validation
- Calendar creation and relationships
- Email uniqueness constraint
- Default calendar linkage
- Preferences JSON field
- Soft deletion behavior
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.family import FamilyMember, Calendar


class TestFamilyMember:
    """Test FamilyMember model functionality."""

    def test_create_family_member(self, db_session: Session):
        """Test creating a basic family member."""
        member = FamilyMember(
            name="Alice Smith",
            email="alice@example.com",
            role="parent",
            preferences={"timezone": "America/Los_Angeles"}
        )
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        assert member.id is not None
        assert member.name == "Alice Smith"
        assert member.email == "alice@example.com"
        assert member.role == "parent"
        assert member.preferences["timezone"] == "America/Los_Angeles"
        assert member.created_at is not None
        assert member.deleted_at is None

    def test_family_member_without_email(self, db_session: Session):
        """Test that email is optional."""
        member = FamilyMember(
            name="Bob Child",
            role="child",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        assert member.id is not None
        assert member.email is None

    def test_family_member_email_unique_constraint(self, db_session: Session):
        """Test that email must be unique."""
        member1 = FamilyMember(
            name="User 1",
            email="same@example.com",
            role="parent",
            preferences={}
        )
        member2 = FamilyMember(
            name="User 2",
            email="same@example.com",
            role="parent",
            preferences={}
        )

        db_session.add(member1)
        db_session.commit()

        db_session.add(member2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_family_member_roles(self, db_session: Session):
        """Test different family member roles."""
        roles = ["parent", "child", "guardian", "other"]

        for role in roles:
            member = FamilyMember(
                name=f"{role.title()} Member",
                role=role,
                preferences={}
            )
            db_session.add(member)

        db_session.commit()

        # Verify all roles were saved
        members = db_session.query(FamilyMember).all()
        assert len(members) == 4
        saved_roles = {m.role for m in members}
        assert saved_roles == set(roles)

    def test_family_member_preferences_json(self, db_session: Session):
        """Test storing complex preferences in JSON field."""
        preferences = {
            "timezone": "America/New_York",
            "work_schedule": {
                "monday": {"start": "09:00", "end": "17:00"},
                "friday": {"start": "09:00", "end": "15:00"}
            },
            "notification_settings": {
                "email": True,
                "sms": False,
                "push": True
            },
            "favorite_colors": ["blue", "green", "red"]
        }

        member = FamilyMember(
            name="Complex User",
            role="parent",
            preferences=preferences
        )
        db_session.add(member)
        db_session.commit()
        db_session.refresh(member)

        # Verify nested structure preserved
        assert member.preferences["timezone"] == "America/New_York"
        assert member.preferences["work_schedule"]["friday"]["end"] == "15:00"
        assert member.preferences["notification_settings"]["sms"] is False
        assert len(member.preferences["favorite_colors"]) == 3

    def test_family_member_default_calendar_relationship(self, db_session: Session):
        """Test default_calendar relationship."""
        member = FamilyMember(
            name="User With Calendar",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Personal Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        # Set as default calendar
        member.default_calendar_id = calendar.id
        db_session.commit()
        db_session.refresh(member)

        # Verify relationship
        assert member.default_calendar_id == calendar.id
        assert member.default_calendar is not None
        assert member.default_calendar.name == "Personal Calendar"

    def test_family_member_multiple_calendars(self, db_session: Session):
        """Test a family member owning multiple calendars."""
        member = FamilyMember(
            name="Calendar Owner",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        calendars = [
            Calendar(
                name="Work Calendar",
                calendar_type="work",
                owner_id=member.id,
                visibility="private"
            ),
            Calendar(
                name="Personal Calendar",
                calendar_type="personal",
                owner_id=member.id,
                visibility="private"
            ),
            Calendar(
                name="Family Calendar",
                calendar_type="family",
                owner_id=member.id,
                visibility="shared"
            ),
        ]

        for cal in calendars:
            db_session.add(cal)
        db_session.commit()
        db_session.refresh(member)

        # Verify owned_calendars relationship
        assert len(member.owned_calendars) == 3
        calendar_names = {c.name for c in member.owned_calendars}
        assert calendar_names == {"Work Calendar", "Personal Calendar", "Family Calendar"}

    def test_family_member_soft_delete(self, db_session: Session):
        """Test soft deletion of family member."""
        member = FamilyMember(
            name="To Delete",
            email="delete@example.com",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()
        member_id = member.id

        # Soft delete
        member.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_member = db_session.query(FamilyMember).filter_by(id=member_id).first()
        assert deleted_member is not None
        assert deleted_member.deleted_at is not None

        # Verify filtered out by active query
        active_members = db_session.query(FamilyMember).filter(
            FamilyMember.deleted_at.is_(None)
        ).all()
        assert deleted_member not in active_members

    def test_family_member_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(
            name="John Doe",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        repr_str = repr(member)
        assert "FamilyMember" in repr_str
        assert "John Doe" in repr_str
        assert "parent" in repr_str


class TestCalendar:
    """Test Calendar model functionality."""

    def test_create_calendar(self, db_session: Session):
        """Test creating a basic calendar."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="My Calendar",
            description="A test calendar",
            calendar_type="personal",
            color="#FF5733",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()
        db_session.refresh(calendar)

        assert calendar.id is not None
        assert calendar.name == "My Calendar"
        assert calendar.description == "A test calendar"
        assert calendar.calendar_type == "personal"
        assert calendar.color == "#FF5733"
        assert calendar.owner_id == member.id
        assert calendar.visibility == "private"
        assert calendar.created_at is not None
        assert calendar.deleted_at is None

    def test_calendar_types(self, db_session: Session):
        """Test different calendar types."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar_types = ["personal", "family", "work", "school", "other"]

        for cal_type in calendar_types:
            calendar = Calendar(
                name=f"{cal_type.title()} Calendar",
                calendar_type=cal_type,
                owner_id=member.id,
                visibility="private"
            )
            db_session.add(calendar)

        db_session.commit()

        # Verify all types saved
        calendars = db_session.query(Calendar).all()
        assert len(calendars) == 5
        saved_types = {c.calendar_type for c in calendars}
        assert saved_types == set(calendar_types)

    def test_calendar_visibility_options(self, db_session: Session):
        """Test calendar visibility settings."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        visibilities = ["private", "shared", "public"]

        for visibility in visibilities:
            calendar = Calendar(
                name=f"{visibility.title()} Calendar",
                calendar_type="personal",
                owner_id=member.id,
                visibility=visibility
            )
            db_session.add(calendar)

        db_session.commit()

        # Verify all visibilities saved
        calendars = db_session.query(Calendar).all()
        saved_visibilities = {c.visibility for c in calendars}
        assert saved_visibilities == set(visibilities)

    def test_calendar_owner_relationship(self, db_session: Session):
        """Test calendar-owner relationship."""
        member = FamilyMember(name="Calendar Owner", role="parent", preferences={})
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
        db_session.refresh(calendar)

        # Verify bidirectional relationship
        assert calendar.owner is not None
        assert calendar.owner.id == member.id
        assert calendar.owner.name == "Calendar Owner"

        assert calendar in member.owned_calendars

    def test_calendar_without_optional_fields(self, db_session: Session):
        """Test creating calendar with only required fields."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Minimal Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        assert calendar.id is not None
        assert calendar.description is None
        # Color has a default value
        assert calendar.color == "#3B82F6"

    def test_calendar_color_validation(self, db_session: Session):
        """Test calendar color field accepts hex colors."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        colors = ["#FF5733", "#00FF00", "#0000FF", "#ABCDEF"]

        for color in colors:
            calendar = Calendar(
                name=f"Calendar {color}",
                calendar_type="personal",
                owner_id=member.id,
                visibility="private",
                color=color
            )
            db_session.add(calendar)

        db_session.commit()

        calendars = db_session.query(Calendar).all()
        saved_colors = {c.color for c in calendars if c.color}
        assert saved_colors == set(colors)

    def test_calendar_soft_delete(self, db_session: Session):
        """Test soft deletion of calendar."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="To Delete",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()
        calendar_id = calendar.id

        # Soft delete
        calendar.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_calendar = db_session.query(Calendar).filter_by(id=calendar_id).first()
        assert deleted_calendar is not None
        assert deleted_calendar.deleted_at is not None

        # Verify filtered out by active query
        active_calendars = db_session.query(Calendar).filter(
            Calendar.deleted_at.is_(None)
        ).all()
        assert deleted_calendar not in active_calendars

    def test_calendar_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Family Calendar",
            calendar_type="family",
            owner_id=member.id,
            visibility="shared"
        )
        db_session.add(calendar)
        db_session.commit()

        repr_str = repr(calendar)
        assert "Calendar" in repr_str
        assert "Family Calendar" in repr_str
        assert "family" in repr_str


class TestFamilyMemberCalendarRelationships:
    """Test relationships between FamilyMember and Calendar."""

    def test_multiple_members_multiple_calendars(self, db_session: Session):
        """Test multiple members each owning multiple calendars."""
        members = [
            FamilyMember(name="Parent 1", role="parent", preferences={}),
            FamilyMember(name="Parent 2", role="parent", preferences={}),
        ]

        for member in members:
            db_session.add(member)
        db_session.commit()

        # Each member gets 2 calendars
        for member in members:
            cal1 = Calendar(
                name=f"{member.name} Work",
                calendar_type="work",
                owner_id=member.id,
                visibility="private"
            )
            cal2 = Calendar(
                name=f"{member.name} Personal",
                calendar_type="personal",
                owner_id=member.id,
                visibility="private"
            )
            db_session.add_all([cal1, cal2])

        db_session.commit()

        # Verify each member has 2 calendars
        for member in members:
            db_session.refresh(member)
            assert len(member.owned_calendars) == 2

        # Verify total of 4 calendars
        total_calendars = db_session.query(Calendar).count()
        assert total_calendars == 4

    def test_default_calendar_among_multiple(self, db_session: Session):
        """Test setting one calendar as default among multiple owned calendars."""
        member = FamilyMember(name="Multi-Calendar User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendars = [
            Calendar(
                name="Calendar 1",
                calendar_type="personal",
                owner_id=member.id,
                visibility="private"
            ),
            Calendar(
                name="Calendar 2",
                calendar_type="work",
                owner_id=member.id,
                visibility="private"
            ),
            Calendar(
                name="Default Calendar",
                calendar_type="family",
                owner_id=member.id,
                visibility="shared"
            ),
        ]

        for cal in calendars:
            db_session.add(cal)
        db_session.commit()

        # Set third calendar as default
        member.default_calendar_id = calendars[2].id
        db_session.commit()
        db_session.refresh(member)

        # Verify correct default calendar
        assert member.default_calendar.name == "Default Calendar"
        assert member.default_calendar.calendar_type == "family"

        # Verify still owns all 3 calendars
        assert len(member.owned_calendars) == 3

    def test_delete_owner_does_not_cascade_to_calendars(self, db_session: Session):
        """Test that soft-deleting member doesn't affect their calendars."""
        member = FamilyMember(name="To Be Deleted", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Orphaned Calendar",
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
        remaining_calendar = db_session.query(Calendar).filter_by(id=calendar_id).first()
        assert remaining_calendar is not None
        assert remaining_calendar.deleted_at is None
        assert remaining_calendar.owner_id == member.id

    def test_query_calendars_by_owner(self, db_session: Session):
        """Test querying calendars by owner."""
        member1 = FamilyMember(name="Owner 1", role="parent", preferences={})
        member2 = FamilyMember(name="Owner 2", role="parent", preferences={})
        db_session.add_all([member1, member2])
        db_session.commit()

        # Create calendars for each owner
        for i in range(3):
            db_session.add(Calendar(
                name=f"Owner 1 Calendar {i}",
                calendar_type="personal",
                owner_id=member1.id,
                visibility="private"
            ))

        for i in range(2):
            db_session.add(Calendar(
                name=f"Owner 2 Calendar {i}",
                calendar_type="personal",
                owner_id=member2.id,
                visibility="private"
            ))

        db_session.commit()

        # Query calendars by owner
        owner1_calendars = db_session.query(Calendar).filter_by(owner_id=member1.id).all()
        owner2_calendars = db_session.query(Calendar).filter_by(owner_id=member2.id).all()

        assert len(owner1_calendars) == 3
        assert len(owner2_calendars) == 2

        # Verify all calendars belong to correct owner
        for cal in owner1_calendars:
            assert cal.owner_id == member1.id
        for cal in owner2_calendars:
            assert cal.owner_id == member2.id
