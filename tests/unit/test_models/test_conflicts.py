"""
Unit tests for Conflict model.

Tests:
- Conflict creation and types
- Severity levels
- Status lifecycle (detected -> resolved/ignored)
- Event relationships (proposed and conflicting)
- Affected entities (participants, resources, constraints)
- Proposed resolutions
- Resolution tracking
- Soft deletion
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from src.models.conflicts import Conflict
from src.models.events import Event
from src.models.family import FamilyMember, Calendar


class TestConflict:
    """Test Conflict model functionality."""

    def test_create_conflict(self, db_session: Session):
        """Test creating a basic conflict."""
        # Setup: Create member, calendar, and events
        member = FamilyMember(name="Test User", role="parent", preferences={})
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

        proposed_event = Event(
            calendar_id=calendar.id,
            title="New Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        existing_event = Event(
            calendar_id=calendar.id,
            title="Existing Appointment",
            start_time=datetime(2026, 2, 15, 10, 30, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 30, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add_all([proposed_event, existing_event])
        db_session.commit()

        # Create conflict
        conflict = Conflict(
            proposed_event_id=proposed_event.id,
            conflicting_event_id=existing_event.id,
            conflict_type="time_conflict",
            severity="high",
            description="Events overlap by 30 minutes",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert conflict.id is not None
        assert conflict.proposed_event_id == proposed_event.id
        assert conflict.conflicting_event_id == existing_event.id
        assert conflict.conflict_type == "time_conflict"
        assert conflict.severity == "high"
        assert conflict.description == "Events overlap by 30 minutes"
        assert str(member.id) in conflict.affected_participants
        assert conflict.status == "detected"
        assert conflict.detected_at is not None
        assert conflict.resolved_at is None
        assert conflict.created_at is not None
        assert conflict.deleted_at is None

    def test_conflict_types(self, db_session: Session):
        """Test different conflict types."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        conflict_types = ["time_conflict", "resource_conflict", "constraint_violation"]

        for i, conflict_type in enumerate(conflict_types):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type=conflict_type,
                severity="medium",
                description=f"Test {conflict_type}",
                affected_participants=[str(member.id)],
                status="detected"
            )
            db_session.add(conflict)

        db_session.commit()

        conflicts = db_session.query(Conflict).all()
        saved_types = {c.conflict_type for c in conflicts}
        assert saved_types == set(conflict_types)

    def test_severity_levels(self, db_session: Session):
        """Test different severity levels."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        severities = ["low", "medium", "high", "critical"]

        for i, severity in enumerate(severities):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity=severity,
                description=f"Test severity {severity}",
                affected_participants=[str(member.id)],
                status="detected"
            )
            db_session.add(conflict)

        db_session.commit()

        conflicts = db_session.query(Conflict).all()
        saved_severities = {c.severity for c in conflicts}
        assert saved_severities == set(severities)

    def test_status_detected(self, db_session: Session):
        """Test conflict in detected status."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Test Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="medium",
            description="Test conflict",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.status == "detected"
        assert conflict.detected_at is not None
        assert conflict.resolved_at is None
        assert conflict.resolution_applied is None
        assert conflict.resolution_method is None

    def test_status_resolved(self, db_session: Session):
        """Test resolving a conflict."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Test Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="medium",
            description="Test conflict",
            affected_participants=[str(member.id)],
            proposed_resolutions={
                "options": [
                    {"id": "res1", "type": "reschedule", "new_time": "14:00"}
                ]
            },
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()

        # Resolve the conflict
        conflict.status = "resolved"
        conflict.resolved_at = datetime.now(timezone.utc)
        conflict.resolution_applied = "res1"
        conflict.resolution_method = "user_manual"
        db_session.commit()

        assert conflict.status == "resolved"
        assert conflict.resolved_at is not None
        assert conflict.resolution_applied == "res1"
        assert conflict.resolution_method == "user_manual"

    def test_status_ignored(self, db_session: Session):
        """Test ignoring a conflict."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Test Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="constraint_violation",
            severity="low",
            description="Soft constraint violation",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()

        # Ignore the conflict
        conflict.status = "ignored"
        conflict.resolved_at = datetime.now(timezone.utc)
        conflict.resolution_method = "user_manual"
        conflict.notes = "User acknowledged and proceeded anyway"
        db_session.commit()

        assert conflict.status == "ignored"
        assert conflict.resolved_at is not None
        assert conflict.notes == "User acknowledged and proceeded anyway"

    def test_constraint_violation_no_conflicting_event(self, db_session: Session):
        """Test constraint violation without a conflicting event."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Early Morning Event",
            start_time=datetime(2026, 2, 15, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 7, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Constraint violation - no conflicting event
        conflict = Conflict(
            proposed_event_id=event.id,
            conflicting_event_id=None,  # No conflicting event
            conflict_type="constraint_violation",
            severity="medium",
            description="Violates 'No Early Morning' constraint",
            affected_participants=[str(member.id)],
            affected_constraints=[str(uuid.uuid4())],  # The violated constraint
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.conflicting_event_id is None
        assert conflict.conflicting_event is None
        assert conflict.affected_constraints is not None
        assert len(conflict.affected_constraints) == 1

    def test_event_relationships(self, db_session: Session):
        """Test conflict-event relationships."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        proposed = Event(
            calendar_id=calendar.id,
            title="Proposed Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        conflicting = Event(
            calendar_id=calendar.id,
            title="Conflicting Event",
            start_time=datetime(2026, 2, 15, 10, 30, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 30, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add_all([proposed, conflicting])
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=proposed.id,
            conflicting_event_id=conflicting.id,
            conflict_type="time_conflict",
            severity="high",
            description="Time overlap",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        # Verify relationships
        assert conflict.proposed_event is not None
        assert conflict.proposed_event.title == "Proposed Event"
        assert conflict.conflicting_event is not None
        assert conflict.conflicting_event.title == "Conflicting Event"

    def test_event_proposed_conflicts_relationship(self, db_session: Session):
        """Test accessing conflicts from proposed event."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Problematic Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Create multiple conflicts for same proposed event
        conflicts = [
            Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity="high",
                description="Time conflict",
                affected_participants=[str(member.id)],
                status="detected"
            ),
            Conflict(
                proposed_event_id=event.id,
                conflict_type="constraint_violation",
                severity="medium",
                description="Constraint violation",
                affected_participants=[str(member.id)],
                status="detected"
            ),
        ]
        db_session.add_all(conflicts)
        db_session.commit()
        db_session.refresh(event)

        assert len(event.proposed_conflicts) == 2

    def test_affected_participants(self, db_session: Session):
        """Test affected participants list."""
        members = [
            FamilyMember(name="Parent 1", role="parent", preferences={}),
            FamilyMember(name="Parent 2", role="parent", preferences={}),
            FamilyMember(name="Child", role="child", preferences={}),
        ]
        db_session.add_all(members)
        db_session.commit()

        calendar = Calendar(
            name="Family Calendar",
            calendar_type="family",
            owner_id=members[0].id,
            visibility="shared"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Family Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=members[0].id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        affected_ids = [str(m.id) for m in members]

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="high",
            description="Affects all family members",
            affected_participants=affected_ids,
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert len(conflict.affected_participants) == 3
        for member_id in affected_ids:
            assert member_id in conflict.affected_participants

    def test_affected_resources(self, db_session: Session):
        """Test affected resources list."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Resource Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        resource_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="resource_conflict",
            severity="high",
            description="Resources over capacity",
            affected_participants=[str(member.id)],
            affected_resources=resource_ids,
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert conflict.affected_resources is not None
        assert len(conflict.affected_resources) == 2

    def test_affected_constraints(self, db_session: Session):
        """Test affected constraints list."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Constraint Violation Event",
            start_time=datetime(2026, 2, 15, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 7, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        constraint_ids = [str(uuid.uuid4())]

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="constraint_violation",
            severity="medium",
            description="Violates early morning constraint",
            affected_participants=[str(member.id)],
            affected_constraints=constraint_ids,
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert conflict.affected_constraints is not None
        assert len(conflict.affected_constraints) == 1

    def test_proposed_resolutions(self, db_session: Session):
        """Test storing proposed resolutions."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        resolutions = {
            "options": [
                {
                    "id": "res1",
                    "type": "reschedule",
                    "new_time": "14:00",
                    "confidence": 0.9,
                    "description": "Move to afternoon"
                },
                {
                    "id": "res2",
                    "type": "cancel",
                    "confidence": 0.3,
                    "description": "Cancel the new event"
                },
                {
                    "id": "res3",
                    "type": "modify_existing",
                    "event_id": str(uuid.uuid4()),
                    "confidence": 0.6,
                    "description": "Shorten existing event"
                }
            ],
            "recommended": "res1"
        }

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="medium",
            description="Time conflict",
            affected_participants=[str(member.id)],
            proposed_resolutions=resolutions,
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        db_session.refresh(conflict)

        assert conflict.proposed_resolutions is not None
        assert len(conflict.proposed_resolutions["options"]) == 3
        assert conflict.proposed_resolutions["recommended"] == "res1"
        assert conflict.proposed_resolutions["options"][0]["confidence"] == 0.9

    def test_resolution_methods(self, db_session: Session):
        """Test different resolution methods."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        methods = ["user_manual", "auto_confirm", "agent_suggested"]

        for i, method in enumerate(methods):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity="medium",
                description=f"Test {method}",
                affected_participants=[str(member.id)],
                status="resolved",
                resolved_at=datetime.now(timezone.utc),
                resolution_method=method
            )
            db_session.add(conflict)

        db_session.commit()

        conflicts = db_session.query(Conflict).filter(
            Conflict.status == "resolved"
        ).all()
        saved_methods = {c.resolution_method for c in conflicts}
        assert saved_methods == set(methods)

    def test_query_conflicts_by_status(self, db_session: Session):
        """Test querying conflicts by status."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        statuses = ["detected", "resolved", "ignored"]

        for i, status in enumerate(statuses):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity="medium",
                description=f"Test {status}",
                affected_participants=[str(member.id)],
                status=status,
                resolved_at=datetime.now(timezone.utc) if status != "detected" else None
            )
            db_session.add(conflict)

        db_session.commit()

        # Query detected conflicts
        detected = db_session.query(Conflict).filter_by(status="detected").all()
        assert len(detected) == 1

        # Query resolved/ignored
        handled = db_session.query(Conflict).filter(
            Conflict.status.in_(["resolved", "ignored"])
        ).all()
        assert len(handled) == 2

    def test_query_conflicts_by_severity(self, db_session: Session):
        """Test querying conflicts by severity."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        # Create conflicts with different severities
        severities = ["low", "medium", "high", "critical", "critical"]

        for i, severity in enumerate(severities):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity=severity,
                description=f"Test {severity}",
                affected_participants=[str(member.id)],
                status="detected"
            )
            db_session.add(conflict)

        db_session.commit()

        # Query critical conflicts
        critical = db_session.query(Conflict).filter_by(severity="critical").all()
        assert len(critical) == 2

        # Query high or critical
        urgent = db_session.query(Conflict).filter(
            Conflict.severity.in_(["high", "critical"])
        ).all()
        assert len(urgent) == 3

    def test_conflict_notes(self, db_session: Session):
        """Test conflict notes field."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="medium",
            description="Time overlap",
            affected_participants=[str(member.id)],
            status="detected",
            notes="User mentioned this is a recurring issue"
        )
        db_session.add(conflict)
        db_session.commit()

        assert conflict.notes == "User mentioned this is a recurring issue"

    def test_conflict_soft_delete(self, db_session: Session):
        """Test soft deletion of conflict."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="medium",
            description="To delete",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()
        conflict_id = conflict.id

        # Soft delete
        conflict.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_conflict = db_session.query(Conflict).filter_by(id=conflict_id).first()
        assert deleted_conflict is not None
        assert deleted_conflict.deleted_at is not None

    def test_query_non_deleted_conflicts(self, db_session: Session):
        """Test querying only non-deleted conflicts."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        for i in range(3):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility="flexible",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.commit()

            conflict = Conflict(
                proposed_event_id=event.id,
                conflict_type="time_conflict",
                severity="medium",
                description=f"Conflict {i}",
                affected_participants=[str(member.id)],
                status="detected",
                deleted_at=datetime.now(timezone.utc) if i == 1 else None
            )
            db_session.add(conflict)

        db_session.commit()

        # Query non-deleted
        non_deleted = db_session.query(Conflict).filter(
            Conflict.deleted_at.is_(None)
        ).all()

        assert len(non_deleted) == 2

    def test_conflict_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(name="Test User", role="parent", preferences={})
        db_session.add(member)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="flexible",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        conflict = Conflict(
            proposed_event_id=event.id,
            conflict_type="time_conflict",
            severity="high",
            description="Test",
            affected_participants=[str(member.id)],
            status="detected"
        )
        db_session.add(conflict)
        db_session.commit()

        repr_str = repr(conflict)
        assert "Conflict" in repr_str
        assert "time_conflict" in repr_str
        assert "high" in repr_str
        assert "detected" in repr_str

    def test_conflict_with_sample_fixture(
        self, db_session: Session, sample_conflict: Conflict
    ):
        """Test using the sample_conflict fixture."""
        assert sample_conflict.id is not None
        assert sample_conflict.conflict_type == "time_overlap"
        assert sample_conflict.severity == "high"
        assert sample_conflict.status == "detected"
        assert sample_conflict.proposed_event is not None
        assert sample_conflict.conflicting_event is not None
