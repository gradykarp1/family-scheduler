"""Tests for Google Calendar adapter."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.integrations.base import CreateEventRequest, FreeBusySlot
from src.integrations.google_calendar.adapter import (
    GoogleCalendarAdapter,
    _format_datetime,
    _parse_date,
    _parse_datetime,
)


class TestDateTimeFormatting:
    """Tests for datetime formatting utilities."""

    def test_format_datetime_utc(self):
        """Should format UTC datetime to RFC 3339."""
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_datetime(dt)
        assert result == "2026-01-15T10:30:00+00:00"

    def test_format_datetime_naive(self):
        """Should treat naive datetime as UTC."""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _format_datetime(dt)
        assert "2026-01-15T10:30:00" in result

    def test_parse_datetime_with_timezone(self):
        """Should parse RFC 3339 datetime with timezone."""
        dt_str = "2026-01-15T10:30:00-08:00"
        result = _parse_datetime(dt_str)
        assert result.tzinfo is not None
        assert result.hour == 10  # Original hour preserved

    def test_parse_datetime_utc(self):
        """Should parse UTC datetime."""
        dt_str = "2026-01-15T10:30:00Z"
        result = _parse_datetime(dt_str)
        assert result.tzinfo is not None
        assert result.hour == 10

    def test_parse_date(self):
        """Should parse date string for all-day events."""
        date_str = "2026-01-15"
        result = _parse_date(date_str)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0


class TestToGoogleEvent:
    """Tests for converting internal events to Google format."""

    def test_basic_event(self):
        """Should convert basic event fields."""
        event = CreateEventRequest(
            title="Team Meeting",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert result["summary"] == "Team Meeting"
        assert "dateTime" in result["start"]
        assert "dateTime" in result["end"]
        assert "2026-01-15T10:00:00" in result["start"]["dateTime"]

    def test_event_with_description_and_location(self):
        """Should include description and location."""
        event = CreateEventRequest(
            title="Conference",
            description="Annual company conference",
            location="Convention Center",
            start_time=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc),
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert result["description"] == "Annual company conference"
        assert result["location"] == "Convention Center"

    def test_all_day_event(self):
        """Should use date format for all-day events."""
        event = CreateEventRequest(
            title="Vacation",
            start_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 16, tzinfo=timezone.utc),
            all_day=True,
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert result["start"] == {"date": "2026-01-15"}
        assert result["end"] == {"date": "2026-01-16"}
        assert "dateTime" not in result["start"]

    def test_event_with_attendees(self):
        """Should include attendees as email list."""
        event = CreateEventRequest(
            title="Meeting",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            attendees=["alice@example.com", "bob@example.com"],
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert len(result["attendees"]) == 2
        assert {"email": "alice@example.com"} in result["attendees"]
        assert {"email": "bob@example.com"} in result["attendees"]

    def test_event_with_recurrence(self):
        """Should include RRULE with prefix."""
        event = CreateEventRequest(
            title="Weekly Standup",
            start_time=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc),
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert result["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"]

    def test_event_with_rrule_prefix(self):
        """Should not double-prefix RRULE."""
        event = CreateEventRequest(
            title="Daily",
            start_time=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=DAILY",
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        assert result["recurrence"] == ["RRULE:FREQ=DAILY"]

    def test_extended_properties(self):
        """Should store custom fields in extendedProperties."""
        event = CreateEventRequest(
            title="Important",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            priority="high",
            flexibility="flexible",
            created_by="user-123",
        )

        result = GoogleCalendarAdapter.to_google_event(event, internal_id="event-456")

        props = result["extendedProperties"]["private"]
        assert props["family_scheduler_id"] == "event-456"
        assert props["priority"] == "high"
        assert props["flexibility"] == "flexible"
        assert props["created_by"] == "user-123"

    def test_metadata_in_extended_properties(self):
        """Should include metadata in extended properties."""
        event = CreateEventRequest(
            title="Event",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            metadata={"custom_field": "custom_value", "count": 42},
        )

        result = GoogleCalendarAdapter.to_google_event(event)

        props = result["extendedProperties"]["private"]
        assert props["custom_field"] == "custom_value"
        assert props["count"] == "42"


class TestFromGoogleEvent:
    """Tests for converting Google events to internal format."""

    def test_basic_event(self):
        """Should parse basic Google event."""
        google_event = {
            "id": "google-event-123",
            "summary": "Team Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert result.id == "google-event-123"
        assert result.calendar_id == "cal-123"
        assert result.title == "Team Meeting"
        assert result.start_time.hour == 10
        assert result.end_time.hour == 11
        assert result.all_day is False

    def test_all_day_event(self):
        """Should parse all-day event."""
        google_event = {
            "id": "event-1",
            "summary": "Holiday",
            "start": {"date": "2026-01-15"},
            "end": {"date": "2026-01-16"},
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert result.all_day is True
        assert result.start_time.day == 15
        assert result.end_time.day == 16

    def test_event_with_attendees(self):
        """Should parse attendees."""
        google_event = {
            "id": "event-1",
            "summary": "Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
            "attendees": [
                {"email": "alice@example.com", "responseStatus": "accepted"},
                {"email": "bob@example.com", "responseStatus": "tentative"},
            ],
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert len(result.attendees) == 2
        assert "alice@example.com" in result.attendees
        assert "bob@example.com" in result.attendees

    def test_event_with_recurrence(self):
        """Should parse recurrence rule."""
        google_event = {
            "id": "event-1",
            "summary": "Recurring",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert result.recurrence_rule == "FREQ=WEEKLY;BYDAY=MO"

    def test_status_mapping(self):
        """Should map Google status to internal status."""
        for google_status, expected in [
            ("tentative", "proposed"),
            ("confirmed", "confirmed"),
            ("cancelled", "cancelled"),
        ]:
            google_event = {
                "id": "event-1",
                "summary": "Event",
                "start": {"dateTime": "2026-01-15T10:00:00Z"},
                "end": {"dateTime": "2026-01-15T11:00:00Z"},
                "status": google_status,
            }

            result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")
            assert result.status == expected

    def test_extended_properties_in_metadata(self):
        """Should include extended properties in metadata."""
        google_event = {
            "id": "event-1",
            "summary": "Event",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
            "etag": '"abc123"',
            "htmlLink": "https://calendar.google.com/event/123",
            "extendedProperties": {
                "private": {
                    "family_scheduler_id": "internal-456",
                    "priority": "high",
                }
            },
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert result.metadata["google_id"] == "event-1"
        assert result.metadata["etag"] == '"abc123"'
        assert result.metadata["family_scheduler_id"] == "internal-456"
        assert result.metadata["priority"] == "high"

    def test_untitled_event(self):
        """Should default to 'Untitled' for missing summary."""
        google_event = {
            "id": "event-1",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        result = GoogleCalendarAdapter.from_google_event(google_event, "cal-123")

        assert result.title == "Untitled"


class TestToUpdateBody:
    """Tests for converting update dicts to Google format."""

    def test_title_update(self):
        """Should convert title to summary."""
        updates = {"title": "New Title"}
        result = GoogleCalendarAdapter.to_update_body(updates)
        assert result == {"summary": "New Title"}

    def test_description_and_location(self):
        """Should pass through description and location."""
        updates = {
            "description": "New description",
            "location": "New location",
        }
        result = GoogleCalendarAdapter.to_update_body(updates)
        assert result["description"] == "New description"
        assert result["location"] == "New location"

    def test_status_mapping(self):
        """Should map internal status to Google status."""
        updates = {"status": "proposed"}
        result = GoogleCalendarAdapter.to_update_body(updates)
        assert result["status"] == "tentative"

    def test_time_update(self):
        """Should format time updates."""
        updates = {
            "start_time": datetime(2026, 1, 20, 14, 0, tzinfo=timezone.utc),
            "end_time": datetime(2026, 1, 20, 15, 0, tzinfo=timezone.utc),
        }
        result = GoogleCalendarAdapter.to_update_body(updates)

        assert "dateTime" in result["start"]
        assert "dateTime" in result["end"]
        assert "2026-01-20T14:00:00" in result["start"]["dateTime"]

    def test_all_day_time_update(self):
        """Should use date format for all-day updates."""
        updates = {
            "start_time": datetime(2026, 1, 20, tzinfo=timezone.utc),
            "end_time": datetime(2026, 1, 21, tzinfo=timezone.utc),
            "all_day": True,
        }
        result = GoogleCalendarAdapter.to_update_body(updates)

        assert result["start"] == {"date": "2026-01-20"}
        assert result["end"] == {"date": "2026-01-21"}

    def test_attendee_update(self):
        """Should format attendee updates."""
        updates = {"attendees": ["alice@example.com", "bob@example.com"]}
        result = GoogleCalendarAdapter.to_update_body(updates)

        assert result["attendees"] == [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ]

    def test_recurrence_update(self):
        """Should format recurrence update."""
        updates = {"recurrence_rule": "FREQ=DAILY"}
        result = GoogleCalendarAdapter.to_update_body(updates)
        assert result["recurrence"] == ["RRULE:FREQ=DAILY"]

    def test_clear_recurrence(self):
        """Should clear recurrence with empty list."""
        updates = {"recurrence_rule": None}
        result = GoogleCalendarAdapter.to_update_body(updates)
        assert result["recurrence"] == []


class TestParseFreebusyResponse:
    """Tests for parsing freebusy API responses."""

    def test_single_calendar_busy_slots(self):
        """Should parse busy slots for single calendar."""
        response = {
            "calendars": {
                "cal-123": {
                    "busy": [
                        {"start": "2026-01-15T10:00:00Z", "end": "2026-01-15T11:00:00Z"},
                        {"start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:30:00Z"},
                    ]
                }
            }
        }

        result = GoogleCalendarAdapter.parse_freebusy_response(response)

        assert "cal-123" in result
        assert len(result["cal-123"]) == 2
        assert result["cal-123"][0].start.hour == 10
        assert result["cal-123"][1].end.hour == 15

    def test_multiple_calendars(self):
        """Should parse busy slots for multiple calendars."""
        response = {
            "calendars": {
                "cal-1": {"busy": [{"start": "2026-01-15T10:00:00Z", "end": "2026-01-15T11:00:00Z"}]},
                "cal-2": {"busy": [{"start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:00:00Z"}]},
            }
        }

        result = GoogleCalendarAdapter.parse_freebusy_response(response)

        assert len(result) == 2
        assert len(result["cal-1"]) == 1
        assert len(result["cal-2"]) == 1

    def test_empty_busy_slots(self):
        """Should handle calendar with no busy slots."""
        response = {"calendars": {"cal-123": {"busy": []}}}

        result = GoogleCalendarAdapter.parse_freebusy_response(response)

        assert result["cal-123"] == []

    def test_empty_response(self):
        """Should handle empty response."""
        response = {"calendars": {}}
        result = GoogleCalendarAdapter.parse_freebusy_response(response)
        assert result == {}
