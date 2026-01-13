"""Tests for Google Calendar Repository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.base import CreateEventRequest
from src.integrations.google_calendar.exceptions import GoogleCalendarNotFoundError
from src.integrations.google_calendar.repository import (
    GoogleCalendarRepository,
    _format_rfc3339,
)


class TestFormatRfc3339:
    """Tests for RFC 3339 formatting utility."""

    def test_format_utc(self):
        """Should format UTC datetime."""
        dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_rfc3339(dt)
        assert "2026-01-15T10:30:00" in result

    def test_format_naive(self):
        """Should treat naive datetime as UTC."""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _format_rfc3339(dt)
        assert "2026-01-15T10:30:00" in result


@pytest.fixture
def mock_auth_manager():
    """Create mock auth manager."""
    manager = MagicMock()
    manager.get_credentials.return_value = MagicMock()
    return manager


@pytest.fixture
def mock_client():
    """Create mock Google Calendar client."""
    return MagicMock()


@pytest.fixture
def repository(mock_auth_manager, mock_client):
    """Create repository with mocked dependencies."""
    with patch(
        "src.integrations.google_calendar.repository.GoogleCalendarClient"
    ) as mock_client_class:
        mock_client_class.return_value = mock_client
        repo = GoogleCalendarRepository(mock_auth_manager)
        repo._client = mock_client  # Inject mock client
        return repo


class TestGetEventsInRange:
    """Tests for get_events_in_range."""

    @pytest.mark.asyncio
    async def test_returns_converted_events(self, repository, mock_client):
        """Should convert Google events to internal format."""
        mock_client.list_all_events.return_value = [
            {
                "id": "event-1",
                "summary": "Meeting",
                "start": {"dateTime": "2026-01-15T10:00:00Z"},
                "end": {"dateTime": "2026-01-15T11:00:00Z"},
            },
            {
                "id": "event-2",
                "summary": "Lunch",
                "start": {"dateTime": "2026-01-15T12:00:00Z"},
                "end": {"dateTime": "2026-01-15T13:00:00Z"},
            },
        ]

        result = await repository.get_events_in_range(
            calendar_id="cal-123",
            start=datetime(2026, 1, 15, tzinfo=timezone.utc),
            end=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )

        assert len(result) == 2
        assert result[0].id == "event-1"
        assert result[0].title == "Meeting"
        assert result[1].id == "event-2"
        assert result[1].title == "Lunch"

    @pytest.mark.asyncio
    async def test_passes_correct_parameters(self, repository, mock_client):
        """Should pass correct time range to client."""
        mock_client.list_all_events.return_value = []

        await repository.get_events_in_range(
            calendar_id="cal-123",
            start=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            end=datetime(2026, 1, 15, 17, 0, tzinfo=timezone.utc),
            include_recurring=False,
        )

        mock_client.list_all_events.assert_called_once()
        call_kwargs = mock_client.list_all_events.call_args.kwargs
        assert call_kwargs["calendar_id"] == "cal-123"
        assert call_kwargs["single_events"] is False

    @pytest.mark.asyncio
    async def test_empty_result(self, repository, mock_client):
        """Should return empty list when no events found."""
        mock_client.list_all_events.return_value = []

        result = await repository.get_events_in_range(
            calendar_id="cal-123",
            start=datetime(2026, 1, 15, tzinfo=timezone.utc),
            end=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )

        assert result == []


class TestGetEventById:
    """Tests for get_event_by_id."""

    @pytest.mark.asyncio
    async def test_returns_converted_event(self, repository, mock_client):
        """Should convert Google event to internal format."""
        mock_client.get_event.return_value = {
            "id": "event-123",
            "summary": "Important Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        result = await repository.get_event_by_id(
            calendar_id="cal-123",
            event_id="event-123",
        )

        assert result is not None
        assert result.id == "event-123"
        assert result.title == "Important Meeting"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repository, mock_client):
        """Should return None when event not found."""
        mock_client.get_event.side_effect = GoogleCalendarNotFoundError("Not found")

        result = await repository.get_event_by_id(
            calendar_id="cal-123",
            event_id="nonexistent",
        )

        assert result is None


class TestCreateEvent:
    """Tests for create_event."""

    @pytest.mark.asyncio
    async def test_creates_and_returns_event(self, repository, mock_client):
        """Should create event and return converted result."""
        mock_client.insert_event.return_value = {
            "id": "new-event-123",
            "summary": "New Meeting",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        event_request = CreateEventRequest(
            title="New Meeting",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
        )

        result = await repository.create_event(
            calendar_id="cal-123",
            event=event_request,
        )

        assert result.id == "new-event-123"
        assert result.title == "New Meeting"
        mock_client.insert_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_converts_event_to_google_format(self, repository, mock_client):
        """Should convert event request to Google format."""
        mock_client.insert_event.return_value = {
            "id": "new-event",
            "summary": "Test",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        event_request = CreateEventRequest(
            title="Test Event",
            description="Test description",
            location="Test location",
            start_time=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            attendees=["alice@example.com"],
        )

        await repository.create_event(calendar_id="cal-123", event=event_request)

        call_args = mock_client.insert_event.call_args
        body = call_args.kwargs["body"]
        assert body["summary"] == "Test Event"
        assert body["description"] == "Test description"
        assert body["location"] == "Test location"


class TestUpdateEvent:
    """Tests for update_event."""

    @pytest.mark.asyncio
    async def test_updates_and_returns_event(self, repository, mock_client):
        """Should update event and return converted result."""
        mock_client.patch_event.return_value = {
            "id": "event-123",
            "summary": "Updated Title",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        result = await repository.update_event(
            calendar_id="cal-123",
            event_id="event-123",
            updates={"title": "Updated Title"},
        )

        assert result.id == "event-123"
        assert result.title == "Updated Title"
        mock_client.patch_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_converts_updates_to_google_format(self, repository, mock_client):
        """Should convert update dict to Google format."""
        mock_client.patch_event.return_value = {
            "id": "event-123",
            "summary": "Event",
            "start": {"dateTime": "2026-01-15T10:00:00Z"},
            "end": {"dateTime": "2026-01-15T11:00:00Z"},
        }

        await repository.update_event(
            calendar_id="cal-123",
            event_id="event-123",
            updates={"title": "New Title", "status": "proposed"},
        )

        call_args = mock_client.patch_event.call_args
        body = call_args.kwargs["body"]
        assert body["summary"] == "New Title"
        assert body["status"] == "tentative"  # proposed -> tentative


class TestDeleteEvent:
    """Tests for delete_event."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, repository, mock_client):
        """Should return True when event deleted."""
        mock_client.delete_event.return_value = None

        result = await repository.delete_event(
            calendar_id="cal-123",
            event_id="event-123",
        )

        assert result is True
        mock_client.delete_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self, repository, mock_client):
        """Should return False when event not found."""
        mock_client.delete_event.side_effect = GoogleCalendarNotFoundError("Not found")

        result = await repository.delete_event(
            calendar_id="cal-123",
            event_id="nonexistent",
        )

        assert result is False


class TestFindFreeBusy:
    """Tests for find_free_busy."""

    @pytest.mark.asyncio
    async def test_returns_busy_slots(self, repository, mock_client):
        """Should return busy slots for calendars."""
        mock_client.freebusy_query.return_value = {
            "calendars": {
                "cal-123": {
                    "busy": [
                        {"start": "2026-01-15T10:00:00Z", "end": "2026-01-15T11:00:00Z"},
                        {"start": "2026-01-15T14:00:00Z", "end": "2026-01-15T15:00:00Z"},
                    ]
                }
            }
        }

        result = await repository.find_free_busy(
            calendar_ids=["cal-123"],
            start=datetime(2026, 1, 15, tzinfo=timezone.utc),
            end=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )

        assert "cal-123" in result
        assert len(result["cal-123"]) == 2
        assert result["cal-123"][0].start.hour == 10

    @pytest.mark.asyncio
    async def test_multiple_calendars(self, repository, mock_client):
        """Should handle multiple calendars."""
        mock_client.freebusy_query.return_value = {
            "calendars": {
                "cal-1": {"busy": [{"start": "2026-01-15T10:00:00Z", "end": "2026-01-15T11:00:00Z"}]},
                "cal-2": {"busy": []},
            }
        }

        result = await repository.find_free_busy(
            calendar_ids=["cal-1", "cal-2"],
            start=datetime(2026, 1, 15, tzinfo=timezone.utc),
            end=datetime(2026, 1, 16, tzinfo=timezone.utc),
        )

        assert len(result) == 2
        assert len(result["cal-1"]) == 1
        assert len(result["cal-2"]) == 0


class TestContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_auth_manager):
        """Should work as async context manager."""
        with patch(
            "src.integrations.google_calendar.repository.GoogleCalendarClient"
        ):
            async with GoogleCalendarRepository(mock_auth_manager) as repo:
                assert repo is not None

    @pytest.mark.asyncio
    async def test_close_shuts_down_executor(self, mock_auth_manager):
        """Should shut down executor on close."""
        with patch(
            "src.integrations.google_calendar.repository.GoogleCalendarClient"
        ):
            repo = GoogleCalendarRepository(mock_auth_manager)
            executor = repo._executor

            await repo.close()

            # Executor should be None after close
            assert repo._executor is None
