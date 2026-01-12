"""
Unit tests for Event and EventParticipant models.

Tests:
- Event creation and field validation
- Event status workflow (proposed, confirmed, cancelled)
- Recurrence relationships (original_event_id, recurrence_rule)
- EventParticipant association object
- Many-to-many relationships between Events and FamilyMembers
- Event metadata JSON field
- Time-based queries
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.events import Event, EventParticipant
from src.models.family import FamilyMember, Calendar


class TestEvent:
    """Test Event model functionality."""

    def test_create_event(self, db_session: Session):
        """Test creating a basic event."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
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

        event = Event(
            calendar_id=calendar.id,
            title="Team Meeting",
            description="Weekly sync",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            all_day=False,
            location="Conference Room A",
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={"meeting_type": "standup"}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.id is not None
        assert event.title == "Team Meeting"
        assert event.description == "Weekly sync"
        assert event.location == "Conference Room A"
        assert event.status == "proposed"
        assert event.priority == "medium"
        assert event.flexibility == "fixed"
        assert event.all_day is False
        assert event.event_metadata["meeting_type"] == "standup"
        assert event.created_at is not None
        assert event.deleted_at is None

    def test_event_all_day(self, db_session: Session):
        """Test creating an all-day event."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Birthday",
            start_time=datetime(2026, 3, 15, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 15, 23, 59, tzinfo=timezone.utc),
            all_day=True,
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        assert event.all_day is True
        assert event.title == "Birthday"

    def test_event_status_values(self, db_session: Session):
        """Test different event status values."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        statuses = ["proposed", "confirmed", "cancelled"]

        for status in statuses:
            event = Event(
                calendar_id=calendar.id,
                title=f"{status.title()} Event",
                start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
                status=status,
                priority="medium",
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)

        db_session.commit()

        events = db_session.query(Event).all()
        saved_statuses = {e.status for e in events}
        assert saved_statuses == set(statuses)

    def test_event_priority_levels(self, db_session: Session):
        """Test different event priority levels."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            event = Event(
                calendar_id=calendar.id,
                title=f"{priority.title()} Priority Event",
                start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority=priority,
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)

        db_session.commit()

        events = db_session.query(Event).all()
        saved_priorities = {e.priority for e in events}
        assert saved_priorities == set(priorities)

    def test_event_flexibility_options(self, db_session: Session):
        """Test event flexibility options."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        flexibility_options = ["fixed", "preferred", "flexible"]

        for flexibility in flexibility_options:
            event = Event(
                calendar_id=calendar.id,
                title=f"{flexibility.title()} Event",
                start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
                status="proposed",
                priority="medium",
                flexibility=flexibility,
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)

        db_session.commit()

        events = db_session.query(Event).all()
        saved_flexibilities = {e.flexibility for e in events}
        assert saved_flexibilities == set(flexibility_options)

    def test_event_recurrence_rule(self, db_session: Session):
        """Test storing RRULE recurrence patterns."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Weekly Team Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.recurrence_rule == "FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=10"
        assert event.original_event_id is None

    def test_event_recurrence_exception(self, db_session: Session):
        """Test creating a recurrence exception."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        # Create recurring event
        recurring_event = Event(
            calendar_id=calendar.id,
            title="Weekly Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="medium",
            flexibility="fixed",
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(recurring_event)
        db_session.commit()

        # Create exception for specific occurrence
        exception_event = Event(
            calendar_id=calendar.id,
            title="Weekly Meeting (Moved)",
            start_time=datetime(2026, 2, 22, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 22, 15, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="medium",
            flexibility="fixed",
            original_event_id=recurring_event.id,
            recurrence_id="20260222T100000",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(exception_event)
        db_session.commit()
        db_session.refresh(exception_event)

        # Verify exception relationship
        assert exception_event.original_event_id == recurring_event.id
        assert exception_event.original_event.title == "Weekly Meeting"
        assert exception_event.recurrence_id == "20260222T100000"

    def test_event_status_timestamps(self, db_session: Session):
        """Test status change timestamps."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Tracked Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Initially proposed
        assert event.proposed_at is not None
        assert event.confirmed_at is None
        assert event.cancelled_at is None

        # Confirm event
        event.status = "confirmed"
        event.confirmed_at = datetime.now(timezone.utc)
        db_session.commit()

        assert event.confirmed_at is not None

    def test_event_metadata_json(self, db_session: Session):
        """Test storing complex metadata in JSON field."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        metadata = {
            "meeting_url": "https://zoom.us/j/123456789",
            "agenda": ["Item 1", "Item 2", "Item 3"],
            "attachments": [
                {"name": "doc.pdf", "url": "https://example.com/doc.pdf"}
            ],
            "reminders": {
                "email": "1 day before",
                "push": "30 minutes before"
            }
        }

        event = Event(
            calendar_id=calendar.id,
            title="Meeting with Metadata",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata=metadata
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        # Verify nested structure preserved
        assert event.event_metadata["meeting_url"] == "https://zoom.us/j/123456789"
        assert len(event.event_metadata["agenda"]) == 3
        assert event.event_metadata["attachments"][0]["name"] == "doc.pdf"
        assert event.event_metadata["reminders"]["email"] == "1 day before"

    def test_event_calendar_relationship(self, db_session: Session):
        """Test event-calendar relationship."""
        member = FamilyMember(name="Owner", role="parent", preferences={})
        calendar = Calendar(
            name="Work Calendar",
            calendar_type="work",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Work Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        # Verify bidirectional relationship
        assert event.calendar is not None
        assert event.calendar.name == "Work Calendar"
        assert event in event.calendar.events

    def test_event_creator_relationship(self, db_session: Session):
        """Test event-creator relationship."""
        creator = FamilyMember(name="Event Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=creator.id,
            visibility="private"
        )
        db_session.add_all([creator, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Created Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=creator.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        assert event.creator is not None
        assert event.creator.name == "Event Creator"

    def test_event_time_range_queries(self, db_session: Session):
        """Test querying events by time range."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        # Create events at different times
        events = [
            Event(
                calendar_id=calendar.id,
                title="Morning Event",
                start_time=datetime(2026, 2, 15, 8, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 9, 0, tzinfo=timezone.utc),
                status="confirmed",
                priority="medium",
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            ),
            Event(
                calendar_id=calendar.id,
                title="Afternoon Event",
                start_time=datetime(2026, 2, 15, 14, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15, 15, 0, tzinfo=timezone.utc),
                status="confirmed",
                priority="medium",
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            ),
            Event(
                calendar_id=calendar.id,
                title="Next Day Event",
                start_time=datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 16, 11, 0, tzinfo=timezone.utc),
                status="confirmed",
                priority="medium",
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            ),
        ]
        db_session.add_all(events)
        db_session.commit()

        # Query events on 2/15
        day_start = datetime(2026, 2, 15, 0, 0, tzinfo=timezone.utc)
        day_end = datetime(2026, 2, 15, 23, 59, 59, tzinfo=timezone.utc)

        feb_15_events = db_session.query(Event).filter(
            Event.start_time >= day_start,
            Event.start_time <= day_end
        ).all()

        assert len(feb_15_events) == 2
        titles = {e.title for e in feb_15_events}
        assert titles == {"Morning Event", "Afternoon Event"}

    def test_event_soft_delete(self, db_session: Session):
        """Test soft deletion of event."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="To Delete",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        # Soft delete
        event.deleted_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify still in database
        deleted_event = db_session.query(Event).filter_by(id=event_id).first()
        assert deleted_event is not None
        assert deleted_event.deleted_at is not None

    def test_event_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(name="Creator", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Important Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        repr_str = repr(event)
        assert "Event" in repr_str
        assert "Important Meeting" in repr_str
        assert "confirmed" in repr_str


class TestEventParticipant:
    """Test EventParticipant association object."""

    def test_add_participant_to_event(self, db_session: Session):
        """Test adding a participant to an event."""
        member = FamilyMember(name="Participant", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Add participant
        participant = EventParticipant(
            event_id=event.id,
            family_member_id=member.id,
            required=True,
            participation_status="accepted"
        )
        db_session.add(participant)
        db_session.commit()
        db_session.refresh(participant)

        assert participant.id is not None
        assert participant.event_id == event.id
        assert participant.family_member_id == member.id
        assert participant.required is True
        assert participant.participation_status == "accepted"

    def test_multiple_participants_for_event(self, db_session: Session):
        """Test adding multiple participants to an event."""
        members = [
            FamilyMember(name="Alice", role="parent", preferences={}),
            FamilyMember(name="Bob", role="parent", preferences={}),
            FamilyMember(name="Charlie", role="child", preferences={}),
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
            title="Family Dinner",
            start_time=datetime(2026, 2, 15, 18, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 19, 30, tzinfo=timezone.utc),
            status="confirmed",
            priority="high",
            flexibility="fixed",
            created_by=members[0].id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Add all members as participants
        for member in members:
            participant = EventParticipant(
                event_id=event.id,
                family_member_id=member.id,
                required=True,
                participation_status="accepted"
            )
            db_session.add(participant)

        db_session.commit()
        db_session.refresh(event)

        # Verify all participants added
        assert len(event.participants) == 3
        participant_names = {p.family_member.name for p in event.participants}
        assert participant_names == {"Alice", "Bob", "Charlie"}

    def test_participation_status_values(self, db_session: Session):
        """Test different participation status values."""
        members = [
            FamilyMember(name="Member 1", role="parent", preferences={}),
            FamilyMember(name="Member 2", role="parent", preferences={}),
            FamilyMember(name="Member 3", role="child", preferences={}),
            FamilyMember(name="Member 4", role="parent", preferences={}),
        ]
        db_session.add_all(members)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="family",
            owner_id=members[0].id,
            visibility="shared"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event with Various Responses",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=members[0].id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        statuses = ["invited", "accepted", "declined", "tentative"]

        for member, status in zip(members, statuses):
            participant = EventParticipant(
                event_id=event.id,
                family_member_id=member.id,
                required=False,
                participation_status=status
            )
            db_session.add(participant)

        db_session.commit()
        db_session.refresh(event)

        # Verify all statuses saved
        saved_statuses = {p.participation_status for p in event.participants}
        assert saved_statuses == set(statuses)

    def test_required_vs_optional_participants(self, db_session: Session):
        """Test required vs optional participant flags."""
        members = [
            FamilyMember(name="Required Member", role="parent", preferences={}),
            FamilyMember(name="Optional Member", role="child", preferences={}),
        ]
        db_session.add_all(members)
        db_session.commit()

        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=members[0].id,
            visibility="private"
        )
        db_session.add(calendar)
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Meeting",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=members[0].id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Add required participant
        required = EventParticipant(
            event_id=event.id,
            family_member_id=members[0].id,
            required=True,
            participation_status="accepted"
        )
        # Add optional participant
        optional = EventParticipant(
            event_id=event.id,
            family_member_id=members[1].id,
            required=False,
            participation_status="tentative"
        )
        db_session.add_all([required, optional])
        db_session.commit()
        db_session.refresh(event)

        # Query required participants
        required_participants = [p for p in event.participants if p.required]
        optional_participants = [p for p in event.participants if not p.required]

        assert len(required_participants) == 1
        assert len(optional_participants) == 1
        assert required_participants[0].family_member.name == "Required Member"

    def test_unique_constraint_event_participant(self, db_session: Session):
        """Test that a member can only participate in an event once."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        # Add participant
        participant1 = EventParticipant(
            event_id=event.id,
            family_member_id=member.id,
            required=True,
            participation_status="accepted"
        )
        db_session.add(participant1)
        db_session.commit()

        # Try to add same participant again
        participant2 = EventParticipant(
            event_id=event.id,
            family_member_id=member.id,
            required=False,
            participation_status="declined"
        )
        db_session.add(participant2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_member_participations_relationship(self, db_session: Session):
        """Test accessing all events a member participates in."""
        member = FamilyMember(name="Busy Member", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        # Create multiple events
        for i in range(3):
            event = Event(
                calendar_id=calendar.id,
                title=f"Event {i+1}",
                start_time=datetime(2026, 2, 15+i, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 2, 15+i, 11, 0, tzinfo=timezone.utc),
                status="confirmed",
                priority="medium",
                flexibility="fixed",
                created_by=member.id,
                event_metadata={}
            )
            db_session.add(event)
            db_session.flush()

            participant = EventParticipant(
                event_id=event.id,
                family_member_id=member.id,
                required=True,
                participation_status="accepted"
            )
            db_session.add(participant)

        db_session.commit()
        db_session.refresh(member)

        # Verify member has 3 participations
        assert len(member.participations) == 3

        # Access events through participations
        event_titles = {p.event.title for p in member.participations}
        assert event_titles == {"Event 1", "Event 2", "Event 3"}

    def test_event_participant_repr(self, db_session: Session):
        """Test string representation."""
        member = FamilyMember(name="Member", role="parent", preferences={})
        calendar = Calendar(
            name="Calendar",
            calendar_type="personal",
            owner_id=member.id,
            visibility="private"
        )
        db_session.add_all([member, calendar])
        db_session.commit()

        event = Event(
            calendar_id=calendar.id,
            title="Event",
            start_time=datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 15, 11, 0, tzinfo=timezone.utc),
            status="proposed",
            priority="medium",
            flexibility="fixed",
            created_by=member.id,
            event_metadata={}
        )
        db_session.add(event)
        db_session.commit()

        participant = EventParticipant(
            event_id=event.id,
            family_member_id=member.id,
            required=True,
            participation_status="accepted"
        )
        db_session.add(participant)
        db_session.commit()

        repr_str = repr(participant)
        assert "EventParticipant" in repr_str
        assert "required=True" in repr_str
