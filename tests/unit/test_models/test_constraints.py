"""
Unit tests for Constraint model.

Tests:
- Constraint creation and types
- Hard vs soft constraint levels
- Priority handling
- Time window denormalization
- Days of week constraints
- Specific date constraints
- Family member relationships
- Active/inactive status
- Soft deletion
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from src.models.constraints import Constraint
from src.models.family import FamilyMember


class TestConstraint:
    """Test Constraint model functionality."""

    def test_create_constraint(self, db_session: Session):
        """Test creating a basic constraint."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="No Early Mornings",
            description="No events before 8am",
            family_member_id=member.id,
            constraint_type="time_window",
            level="soft",
            priority=7,
            rule={
                "type": "blocked_time",
                "start": "00:00",
                "end": "08:00"
            },
            time_window_start="00:00",
            time_window_end="08:00",
            active=True
        )
        db_session.add(constraint)
        db_session.commit()
        db_session.refresh(constraint)

        assert constraint.id is not None
        assert constraint.name == "No Early Mornings"
        assert constraint.description == "No events before 8am"
        assert constraint.family_member_id == member.id
        assert constraint.constraint_type == "time_window"
        assert constraint.level == "soft"
        assert constraint.priority == 7
        assert constraint.rule["type"] == "blocked_time"
        assert constraint.time_window_start == "00:00"
        assert constraint.time_window_end == "08:00"
        assert constraint.active is True
        assert constraint.created_at is not None
        assert constraint.deleted_at is None

    def test_constraint_types(self, db_session: Session):
        """Test different constraint types."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint_types = [
            ("time_window", {"type": "blocked_time", "start": "00:00", "end": "06:00"}),
            ("min_gap", {"type": "min_gap", "minutes": 30}),
            ("max_events_per_day", {"type": "max_events", "max": 5}),
            ("resource_priority", {"type": "resource_pref", "resource_id": str(uuid.uuid4())}),
            ("custom", {"type": "custom", "expression": "not_on_holidays"})
        ]

        for constraint_type, rule in constraint_types:
            constraint = Constraint(
                name=f"Test {constraint_type}",
                constraint_type=constraint_type,
                level="soft",
                priority=5,
                rule=rule,
                family_member_id=member.id,
                active=True
            )
            db_session.add(constraint)

        db_session.commit()

        constraints = db_session.query(Constraint).all()
        saved_types = {c.constraint_type for c in constraints}
        assert saved_types == {ct[0] for ct in constraint_types}

    def test_hard_constraint(self, db_session: Session):
        """Test hard (blocking) constraint."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="Work Hours",
            description="Absolutely no events during work",
            family_member_id=member.id,
            constraint_type="time_window",
            level="hard",
            priority=10,
            rule={"type": "blocked_time", "start": "09:00", "end": "17:00"},
            time_window_start="09:00",
            time_window_end="17:00",
            days_of_week=[0, 1, 2, 3, 4],  # Monday-Friday
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.level == "hard"
        assert constraint.priority == 10

    def test_soft_constraint(self, db_session: Session):
        """Test soft (preference) constraint."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="Prefer Afternoons",
            description="Prefer afternoon appointments",
            family_member_id=member.id,
            constraint_type="time_window",
            level="soft",
            priority=3,
            rule={"type": "preferred_time", "start": "13:00", "end": "17:00"},
            time_window_start="13:00",
            time_window_end="17:00",
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.level == "soft"
        assert constraint.priority == 3

    def test_constraint_priority_range(self, db_session: Session):
        """Test constraint priority values."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        priorities = [1, 5, 10]

        for priority in priorities:
            constraint = Constraint(
                name=f"Priority {priority}",
                constraint_type="custom",
                level="soft",
                priority=priority,
                rule={"type": "custom"},
                family_member_id=member.id,
                active=True
            )
            db_session.add(constraint)

        db_session.commit()

        constraints = db_session.query(Constraint).order_by(Constraint.priority).all()
        assert [c.priority for c in constraints] == [1, 5, 10]

    def test_constraint_default_priority(self, db_session: Session):
        """Test default priority value (5)."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="Default Priority",
            constraint_type="custom",
            level="soft",
            rule={"type": "custom"},
            family_member_id=member.id,
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.priority == 5

    def test_family_wide_constraint(self, db_session: Session):
        """Test family-wide constraint (no specific member)."""
        constraint = Constraint(
            name="Family Dinner Time",
            description="No events during family dinner",
            family_member_id=None,  # Family-wide
            constraint_type="time_window",
            level="soft",
            priority=8,
            rule={"type": "blocked_time", "start": "18:00", "end": "19:00"},
            time_window_start="18:00",
            time_window_end="19:00",
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.family_member_id is None
        assert constraint.family_member is None

    def test_constraint_family_member_relationship(self, db_session: Session):
        """Test constraint-family member relationship."""
        member = FamilyMember(
            name="Test Parent",
            email="parent@example.com",
            role="parent",
            preferences={}
        )
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="Personal Constraint",
            constraint_type="time_window",
            level="hard",
            priority=10,
            rule={"type": "blocked_time", "start": "09:00", "end": "17:00"},
            family_member_id=member.id,
            active=True
        )
        db_session.add(constraint)
        db_session.commit()
        db_session.refresh(constraint)

        # Verify relationship
        assert constraint.family_member is not None
        assert constraint.family_member.name == "Test Parent"
        assert constraint.family_member.email == "parent@example.com"

    def test_member_constraints_relationship(self, db_session: Session):
        """Test accessing constraints from family member."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        # Create multiple constraints for same member
        constraints = [
            Constraint(
                name="Morning Block",
                constraint_type="time_window",
                level="hard",
                rule={"type": "blocked_time"},
                family_member_id=member.id,
                active=True
            ),
            Constraint(
                name="Lunch Preference",
                constraint_type="time_window",
                level="soft",
                rule={"type": "preferred_time"},
                family_member_id=member.id,
                active=True
            ),
        ]

        for c in constraints:
            db_session.add(c)

        db_session.commit()
        db_session.refresh(member)

        assert len(member.constraints) == 2

    def test_time_window_denormalization(self, db_session: Session):
        """Test time window fields for query optimization."""
        constraint = Constraint(
            name="Office Hours",
            constraint_type="time_window",
            level="hard",
            priority=10,
            rule={"type": "blocked_time", "start": "09:00", "end": "17:00"},
            time_window_start="09:00",
            time_window_end="17:00",
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        # Query by time window
        result = db_session.query(Constraint).filter(
            Constraint.time_window_start == "09:00",
            Constraint.time_window_end == "17:00"
        ).first()

        assert result is not None
        assert result.name == "Office Hours"

    def test_days_of_week_constraint(self, db_session: Session):
        """Test days of week constraint field."""
        constraint = Constraint(
            name="Weekday Only",
            constraint_type="time_window",
            level="hard",
            rule={"type": "blocked_time"},
            days_of_week=[0, 1, 2, 3, 4],  # Monday-Friday (0=Monday)
            active=True
        )
        db_session.add(constraint)
        db_session.commit()
        db_session.refresh(constraint)

        assert constraint.days_of_week == [0, 1, 2, 3, 4]

    def test_specific_date_constraint(self, db_session: Session):
        """Test one-time constraint for specific date."""
        constraint = Constraint(
            name="Birthday Block",
            description="No events on birthday",
            constraint_type="time_window",
            level="hard",
            rule={"type": "blocked_day"},
            specific_date="2026-03-15",
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.specific_date == "2026-03-15"
        assert constraint.days_of_week is None

    def test_constraint_active_inactive(self, db_session: Session):
        """Test active and inactive constraints."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        active_constraint = Constraint(
            name="Active Constraint",
            constraint_type="custom",
            level="soft",
            rule={"type": "custom"},
            family_member_id=member.id,
            active=True
        )
        inactive_constraint = Constraint(
            name="Inactive Constraint",
            constraint_type="custom",
            level="soft",
            rule={"type": "custom"},
            family_member_id=member.id,
            active=False
        )

        db_session.add_all([active_constraint, inactive_constraint])
        db_session.commit()

        # Query only active constraints
        active_constraints = db_session.query(Constraint).filter_by(active=True).all()
        assert len(active_constraints) == 1
        assert active_constraints[0].name == "Active Constraint"

    def test_query_constraints_by_member_and_active(self, db_session: Session):
        """Test composite index query for active constraints by member."""
        member1 = FamilyMember(name="Member 1", role="parent", preferences={})
        member2 = FamilyMember(name="Member 2", role="parent", preferences={})
        db_session.add_all([member1, member2])
        db_session.commit()

        # Create constraints for both members
        constraints = [
            Constraint(
                name="M1 Active",
                constraint_type="custom",
                level="soft",
                rule={},
                family_member_id=member1.id,
                active=True
            ),
            Constraint(
                name="M1 Inactive",
                constraint_type="custom",
                level="soft",
                rule={},
                family_member_id=member1.id,
                active=False
            ),
            Constraint(
                name="M2 Active",
                constraint_type="custom",
                level="soft",
                rule={},
                family_member_id=member2.id,
                active=True
            ),
        ]
        db_session.add_all(constraints)
        db_session.commit()

        # Query active constraints for member1
        m1_active = db_session.query(Constraint).filter(
            Constraint.family_member_id == member1.id,
            Constraint.active == True
        ).all()

        assert len(m1_active) == 1
        assert m1_active[0].name == "M1 Active"

    def test_constraint_rule_json_structure(self, db_session: Session):
        """Test complex rule structure in JSON field."""
        rule = {
            "type": "time_window",
            "windows": [
                {"start": "09:00", "end": "12:00", "preference": "blocked"},
                {"start": "13:00", "end": "17:00", "preference": "preferred"}
            ],
            "exceptions": ["holidays", "weekends"],
            "metadata": {
                "reason": "work schedule",
                "created_by": "user"
            }
        }

        constraint = Constraint(
            name="Complex Rule",
            constraint_type="time_window",
            level="soft",
            priority=5,
            rule=rule,
            active=True
        )
        db_session.add(constraint)
        db_session.commit()
        db_session.refresh(constraint)

        # Verify nested structure preserved
        assert constraint.rule["type"] == "time_window"
        assert len(constraint.rule["windows"]) == 2
        assert constraint.rule["windows"][0]["start"] == "09:00"
        assert "holidays" in constraint.rule["exceptions"]
        assert constraint.rule["metadata"]["reason"] == "work schedule"

    def test_min_gap_constraint(self, db_session: Session):
        """Test minimum gap between events constraint."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="30 Min Gap",
            description="Need 30 minutes between events",
            family_member_id=member.id,
            constraint_type="min_gap",
            level="soft",
            priority=6,
            rule={"type": "min_gap", "minutes": 30},
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.constraint_type == "min_gap"
        assert constraint.rule["minutes"] == 30

    def test_max_events_per_day_constraint(self, db_session: Session):
        """Test maximum events per day constraint."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        constraint = Constraint(
            name="Event Limit",
            description="No more than 5 events per day",
            family_member_id=member.id,
            constraint_type="max_events_per_day",
            level="hard",
            priority=8,
            rule={"type": "max_events", "max": 5},
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        assert constraint.constraint_type == "max_events_per_day"
        assert constraint.rule["max"] == 5

    def test_constraint_soft_delete(self, db_session: Session):
        """Test soft deletion of constraint."""
        constraint = Constraint(
            name="To Delete",
            constraint_type="custom",
            level="soft",
            rule={"type": "custom"},
            active=True
        )
        db_session.add(constraint)
        db_session.commit()
        constraint_id = constraint.id

        # Soft delete
        constraint.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_constraint = db_session.query(Constraint).filter_by(id=constraint_id).first()
        assert deleted_constraint is not None
        assert deleted_constraint.deleted_at is not None

    def test_query_non_deleted_constraints(self, db_session: Session):
        """Test querying only non-deleted constraints."""
        constraints = [
            Constraint(
                name="Active 1",
                constraint_type="custom",
                level="soft",
                rule={},
                active=True
            ),
            Constraint(
                name="Deleted",
                constraint_type="custom",
                level="soft",
                rule={},
                active=True,
                deleted_at=datetime.now(timezone.utc)
            ),
            Constraint(
                name="Active 2",
                constraint_type="custom",
                level="soft",
                rule={},
                active=True
            ),
        ]
        db_session.add_all(constraints)
        db_session.commit()

        # Query non-deleted
        non_deleted = db_session.query(Constraint).filter(
            Constraint.deleted_at.is_(None)
        ).all()

        assert len(non_deleted) == 2
        names = {c.name for c in non_deleted}
        assert names == {"Active 1", "Active 2"}

    def test_constraint_repr(self, db_session: Session):
        """Test string representation."""
        constraint = Constraint(
            name="Test Constraint",
            constraint_type="time_window",
            level="hard",
            rule={"type": "blocked_time"},
            active=True
        )
        db_session.add(constraint)
        db_session.commit()

        repr_str = repr(constraint)
        assert "Constraint" in repr_str
        assert "Test Constraint" in repr_str
        assert "hard" in repr_str
        assert "time_window" in repr_str

    def test_constraint_with_sample_fixture(
        self, db_session: Session, sample_constraint: Constraint
    ):
        """Test using the sample_constraint fixture."""
        assert sample_constraint.id is not None
        assert sample_constraint.name == "Work Hours"
        assert sample_constraint.level == "hard"
        assert sample_constraint.constraint_type == "availability"
        assert sample_constraint.family_member is not None
