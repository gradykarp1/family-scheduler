"""
Unit tests for the queries service.

Tests event and calendar query functions.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.models.family import FamilyMember, Calendar
from src.models.events import Event, EventParticipant
from src.models.conflicts import Conflict
from src.services.queries import (
    get_events_in_range,
    get_events_for_member,
    get_event_by_id,
    find_overlapping_events,
    get_upcoming_events,
    get_member_schedule,
    find_busy_members,
    find_available_members,
    get_unresolved_conflicts,
    get_calendar_by_id,
)


@pytest.fixture
def members(db_session):
    """Create test family members."""
    mom = FamilyMember(
        name="Mom",
        email="mom@test.com",
        role="parent",
    )
    dad = FamilyMember(
        name="Dad",
        email="dad@test.com",
        role="parent",
    )
    kid = FamilyMember(
        name="Kid",
        email="kid@test.com",
        role="child",
    )
    db_session.add_all([mom, dad, kid])
    db_session.commit()
    return {"mom": mom, "dad": dad, "kid": kid}


@pytest.fixture
def calendar(db_session, members):
    """Create a test calendar."""
    cal = Calendar(
        owner_id=members["mom"].id,
        name="Family Calendar",
        calendar_type="family",
    )
    db_session.add(cal)
    db_session.commit()
    return cal


@pytest.fixture
def events(db_session, calendar, members):
    """Create test events."""
    now = datetime.utcnow()

    event1 = Event(
        calendar_id=calendar.id,
        title="Morning Meeting",
        start_time=now + timedelta(days=1, hours=9),
        end_time=now + timedelta(days=1, hours=10),
        status="confirmed",
        created_by=members["mom"].id,
    )
    event2 = Event(
        calendar_id=calendar.id,
        title="Lunch",
        start_time=now + timedelta(days=1, hours=12),
        end_time=now + timedelta(days=1, hours=13),
        status="confirmed",
        created_by=members["mom"].id,
    )
    event3 = Event(
        calendar_id=calendar.id,
        title="Proposed Event",
        start_time=now + timedelta(days=2, hours=14),
        end_time=now + timedelta(days=2, hours=15),
        status="proposed",
        created_by=members["dad"].id,
    )
    event4 = Event(
        calendar_id=calendar.id,
        title="Cancelled Event",
        start_time=now + timedelta(days=3, hours=10),
        end_time=now + timedelta(days=3, hours=11),
        status="cancelled",
        created_by=members["mom"].id,
    )

    db_session.add_all([event1, event2, event3, event4])
    db_session.commit()

    # Add participants
    db_session.add(EventParticipant(event_id=event1.id, family_member_id=members["mom"].id))
    db_session.add(EventParticipant(event_id=event1.id, family_member_id=members["dad"].id))
    db_session.add(EventParticipant(event_id=event2.id, family_member_id=members["kid"].id))
    db_session.commit()

    return {"meeting": event1, "lunch": event2, "proposed": event3, "cancelled": event4}


class TestGetEventsInRange:
    """Test get_events_in_range function."""

    def test_get_events_in_range(self, db_session, calendar, events):
        """Test getting events within a time range."""
        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=3)  # Extended to include proposed event on day 2

        result = get_events_in_range(db_session, calendar.id, start, end)

        # Should include meeting, lunch, and proposed (not cancelled)
        assert len(result) == 3
        titles = {e.title for e in result}
        assert "Morning Meeting" in titles
        assert "Lunch" in titles
        assert "Proposed Event" in titles

    def test_exclude_proposed(self, db_session, calendar, events):
        """Test excluding proposed events."""
        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=3)

        result = get_events_in_range(
            db_session, calendar.id, start, end, include_proposed=False
        )

        titles = {e.title for e in result}
        assert "Proposed Event" not in titles

    def test_include_cancelled(self, db_session, calendar, events):
        """Test including cancelled events."""
        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=4)

        result = get_events_in_range(
            db_session, calendar.id, start, end, include_cancelled=True
        )

        titles = {e.title for e in result}
        assert "Cancelled Event" in titles

    def test_events_ordered_by_start_time(self, db_session, calendar, events):
        """Test events are returned in chronological order."""
        now = datetime.utcnow()
        start = now + timedelta(days=1)
        end = now + timedelta(days=2)

        result = get_events_in_range(db_session, calendar.id, start, end)

        for i in range(len(result) - 1):
            assert result[i].start_time <= result[i + 1].start_time


class TestGetEventsForMember:
    """Test get_events_for_member function."""

    def test_get_member_events(self, db_session, members, events):
        """Test getting events for a specific member."""
        now = datetime.utcnow()
        start = now
        end = now + timedelta(days=5)

        result = get_events_for_member(
            db_session, members["mom"].id, start, end
        )

        # Mom participates in Morning Meeting
        assert len(result) >= 1
        titles = {e.title for e in result}
        assert "Morning Meeting" in titles

    def test_member_with_no_events(self, db_session, members):
        """Test member with no events."""
        now = datetime.utcnow()

        result = get_events_for_member(
            db_session, members["kid"].id, now - timedelta(days=30), now - timedelta(days=1)
        )

        assert len(result) == 0


class TestGetEventById:
    """Test get_event_by_id function."""

    def test_get_existing_event(self, db_session, events):
        """Test getting an existing event."""
        result = get_event_by_id(db_session, events["meeting"].id)

        assert result is not None
        assert result.title == "Morning Meeting"
        assert result.participants is not None  # Relationship loaded

    def test_get_nonexistent_event(self, db_session):
        """Test getting a non-existent event."""
        result = get_event_by_id(db_session, uuid4())
        assert result is None

    def test_exclude_deleted_by_default(self, db_session, events):
        """Test that soft-deleted events are excluded by default."""
        # Soft delete the event
        events["meeting"].deleted_at = datetime.utcnow()
        db_session.commit()

        result = get_event_by_id(db_session, events["meeting"].id)
        assert result is None

    def test_include_deleted(self, db_session, events):
        """Test including soft-deleted events."""
        events["meeting"].deleted_at = datetime.utcnow()
        db_session.commit()

        result = get_event_by_id(db_session, events["meeting"].id, include_deleted=True)
        assert result is not None


class TestFindOverlappingEvents:
    """Test find_overlapping_events function."""

    def test_find_overlapping(self, db_session, calendar, events):
        """Test finding events that overlap with a time slot."""
        # Get time of the morning meeting
        meeting_start = events["meeting"].start_time
        meeting_end = events["meeting"].end_time

        # Check for overlap starting in the middle of the meeting
        result = find_overlapping_events(
            db_session,
            calendar.id,
            meeting_start + timedelta(minutes=30),
            meeting_end + timedelta(minutes=30),
        )

        assert len(result) >= 1
        assert any(e.id == events["meeting"].id for e in result)

    def test_no_overlap(self, db_session, calendar, events):
        """Test when there's no overlap."""
        now = datetime.utcnow()

        result = find_overlapping_events(
            db_session,
            calendar.id,
            now + timedelta(days=10),
            now + timedelta(days=10, hours=1),
        )

        assert len(result) == 0

    def test_exclude_specific_event(self, db_session, calendar, events):
        """Test excluding a specific event from overlap check."""
        meeting = events["meeting"]

        result = find_overlapping_events(
            db_session,
            calendar.id,
            meeting.start_time,
            meeting.end_time,
            exclude_event_id=meeting.id,
        )

        assert not any(e.id == meeting.id for e in result)


class TestGetUpcomingEvents:
    """Test get_upcoming_events function."""

    def test_get_upcoming(self, db_session, calendar, events):
        """Test getting upcoming events."""
        now = datetime.utcnow()

        result = get_upcoming_events(db_session, calendar.id, limit=10, after=now)

        # Only confirmed events
        assert all(e.status == "confirmed" for e in result)
        assert all(e.start_time >= now for e in result)

    def test_limit_results(self, db_session, calendar, events):
        """Test that limit is respected."""
        now = datetime.utcnow()

        result = get_upcoming_events(db_session, calendar.id, limit=1, after=now)

        assert len(result) <= 1


class TestMemberScheduleQueries:
    """Test member schedule query functions."""

    def test_find_busy_members(self, db_session, members, events):
        """Test finding members who are busy during a time slot."""
        meeting = events["meeting"]
        member_ids = [members["mom"].id, members["dad"].id, members["kid"].id]

        busy = find_busy_members(
            db_session,
            member_ids,
            meeting.start_time,
            meeting.end_time,
        )

        # Mom and Dad are in the meeting
        assert members["mom"].id in busy
        assert members["dad"].id in busy

    def test_find_available_members(self, db_session, members, events):
        """Test finding members who are available during a time slot."""
        meeting = events["meeting"]
        member_ids = [members["mom"].id, members["dad"].id, members["kid"].id]

        available = find_available_members(
            db_session,
            member_ids,
            meeting.start_time,
            meeting.end_time,
        )

        # Kid is not in the meeting
        assert members["kid"].id in available


class TestConflictQueries:
    """Test conflict query functions."""

    def test_get_unresolved_conflicts(self, db_session, calendar, members, events):
        """Test getting unresolved conflicts."""
        # Create a conflict
        conflict = Conflict(
            proposed_event_id=events["proposed"].id,
            conflicting_event_id=events["meeting"].id,
            conflict_type="time_overlap",
            severity="high",
            description="Events overlap in time",
            affected_participants=[str(members["mom"].id)],
            status="detected",
        )
        db_session.add(conflict)
        db_session.commit()

        result = get_unresolved_conflicts(db_session)

        assert len(result) >= 1
        assert any(c.id == conflict.id for c in result)

    def test_get_conflicts_for_event(self, db_session, calendar, members, events):
        """Test getting conflicts for a specific event."""
        conflict = Conflict(
            proposed_event_id=events["proposed"].id,
            conflicting_event_id=events["meeting"].id,
            conflict_type="time_overlap",
            severity="high",
            description="Events overlap in time",
            affected_participants=[str(members["mom"].id)],
            status="detected",
        )
        db_session.add(conflict)
        db_session.commit()

        result = get_unresolved_conflicts(db_session, event_id=events["proposed"].id)

        assert len(result) >= 1


class TestCalendarQueries:
    """Test calendar query functions."""

    def test_get_calendar_by_id(self, db_session, calendar):
        """Test getting a calendar by ID."""
        result = get_calendar_by_id(db_session, calendar.id)

        assert result is not None
        assert result.name == "Family Calendar"

    def test_get_nonexistent_calendar(self, db_session):
        """Test getting a non-existent calendar."""
        result = get_calendar_by_id(db_session, uuid4())
        assert result is None
