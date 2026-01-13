"""Tests for Google Calendar API client."""

from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.integrations.google_calendar.client import (
    GoogleCalendarClient,
    _handle_http_error,
    _is_retryable_error,
)
from src.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
    GoogleCalendarConflictError,
    GoogleCalendarError,
    GoogleCalendarNotFoundError,
    GoogleCalendarQuotaError,
    GoogleCalendarRateLimitError,
)


def make_http_error(status: int, message: str = "Error") -> HttpError:
    """Create a mock HttpError for testing."""
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=message.encode())


class TestIsRetryableError:
    """Tests for retry decision logic."""

    def test_retryable_google_calendar_error(self):
        """Should return True for retryable GoogleCalendarError."""
        error = GoogleCalendarQuotaError("Quota exceeded")
        assert _is_retryable_error(error) is True

    def test_non_retryable_google_calendar_error(self):
        """Should return False for non-retryable GoogleCalendarError."""
        error = GoogleCalendarAuthError("Auth failed")
        assert _is_retryable_error(error) is False

    def test_retryable_http_status_codes(self):
        """Should return True for 429, 500, 503 HTTP errors."""
        for status in [429, 500, 503]:
            error = make_http_error(status)
            assert _is_retryable_error(error) is True

    def test_non_retryable_http_status_codes(self):
        """Should return False for other HTTP errors."""
        for status in [400, 401, 403, 404, 409]:
            error = make_http_error(status)
            assert _is_retryable_error(error) is False

    def test_other_exceptions(self):
        """Should return False for non-HTTP exceptions."""
        assert _is_retryable_error(ValueError("test")) is False
        assert _is_retryable_error(RuntimeError("test")) is False


class TestHandleHttpError:
    """Tests for HTTP error to exception mapping."""

    def test_401_auth_error(self):
        """Should raise GoogleCalendarAuthError for 401."""
        error = make_http_error(401)
        with pytest.raises(GoogleCalendarAuthError) as exc_info:
            _handle_http_error(error)
        assert "credentials may be invalid or expired" in str(exc_info.value)

    def test_403_quota_error(self):
        """Should raise GoogleCalendarQuotaError for 403 with quota message."""
        error = make_http_error(403, "quota exceeded")
        with pytest.raises(GoogleCalendarQuotaError) as exc_info:
            _handle_http_error(error)
        assert "quota exceeded" in str(exc_info.value).lower()

    def test_403_rate_limit_error(self):
        """Should raise GoogleCalendarQuotaError for 403 with rate limit message."""
        error = make_http_error(403, "rate limit")
        with pytest.raises(GoogleCalendarQuotaError):
            _handle_http_error(error)

    def test_403_auth_error(self):
        """Should raise GoogleCalendarAuthError for 403 without quota/rate limit."""
        error = make_http_error(403, "Access denied")
        with pytest.raises(GoogleCalendarAuthError) as exc_info:
            _handle_http_error(error)
        assert "sharing permissions" in str(exc_info.value)

    def test_404_not_found(self):
        """Should raise GoogleCalendarNotFoundError for 404."""
        error = make_http_error(404)
        with pytest.raises(GoogleCalendarNotFoundError) as exc_info:
            _handle_http_error(error)
        assert "not found" in str(exc_info.value)

    def test_409_conflict(self):
        """Should raise GoogleCalendarConflictError for 409."""
        error = make_http_error(409)
        with pytest.raises(GoogleCalendarConflictError) as exc_info:
            _handle_http_error(error)
        assert "modified by another process" in str(exc_info.value)

    def test_429_rate_limit(self):
        """Should raise GoogleCalendarRateLimitError for 429."""
        error = make_http_error(429)
        with pytest.raises(GoogleCalendarRateLimitError) as exc_info:
            _handle_http_error(error)
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_generic_error(self):
        """Should raise GoogleCalendarError for other status codes."""
        error = make_http_error(500, "Internal Server Error")
        with pytest.raises(GoogleCalendarError) as exc_info:
            _handle_http_error(error)
        assert "500" in str(exc_info.value)


class TestGoogleCalendarClient:
    """Tests for GoogleCalendarClient operations."""

    @pytest.fixture
    def mock_service(self):
        """Create mock Google Calendar service."""
        with patch("src.integrations.google_calendar.client.build") as mock_build:
            service = MagicMock()
            mock_build.return_value = service
            yield service

    @pytest.fixture
    def client(self, mock_service):
        """Create client with mocked service."""
        credentials = MagicMock()
        return GoogleCalendarClient(credentials)

    def test_list_events(self, client, mock_service):
        """Should list events with correct parameters."""
        mock_response = {
            "items": [{"id": "event-1", "summary": "Test"}],
            "nextPageToken": None,
        }
        mock_service.events().list().execute.return_value = mock_response

        result = client.list_events(
            calendar_id="cal-123",
            time_min="2026-01-15T00:00:00Z",
            time_max="2026-01-16T00:00:00Z",
        )

        assert result == mock_response
        mock_service.events().list.assert_called()

    def test_list_all_events_pagination(self, client, mock_service):
        """Should handle pagination when listing all events."""
        # First page
        page1 = {
            "items": [{"id": "event-1"}],
            "nextPageToken": "token-1",
        }
        # Second page
        page2 = {
            "items": [{"id": "event-2"}],
            "nextPageToken": None,
        }
        mock_service.events().list().execute.side_effect = [page1, page2]

        result = client.list_all_events(
            calendar_id="cal-123",
            time_min="2026-01-15T00:00:00Z",
            time_max="2026-01-16T00:00:00Z",
        )

        assert len(result) == 2
        assert result[0]["id"] == "event-1"
        assert result[1]["id"] == "event-2"

    def test_get_event(self, client, mock_service):
        """Should get single event by ID."""
        mock_event = {"id": "event-123", "summary": "Test Event"}
        mock_service.events().get().execute.return_value = mock_event

        result = client.get_event(calendar_id="cal-123", event_id="event-123")

        assert result == mock_event
        mock_service.events().get.assert_called()

    def test_insert_event(self, client, mock_service):
        """Should create new event."""
        event_body = {"summary": "New Event", "start": {}, "end": {}}
        mock_created = {"id": "new-event-123", **event_body}
        mock_service.events().insert().execute.return_value = mock_created

        result = client.insert_event(calendar_id="cal-123", body=event_body)

        assert result["id"] == "new-event-123"
        mock_service.events().insert.assert_called()

    def test_update_event(self, client, mock_service):
        """Should update existing event."""
        update_body = {"summary": "Updated Event"}
        mock_updated = {"id": "event-123", **update_body}
        mock_service.events().update().execute.return_value = mock_updated

        result = client.update_event(
            calendar_id="cal-123",
            event_id="event-123",
            body=update_body,
        )

        assert result["summary"] == "Updated Event"
        mock_service.events().update.assert_called()

    def test_patch_event(self, client, mock_service):
        """Should patch event with partial update."""
        patch_body = {"summary": "Patched Event"}
        mock_patched = {"id": "event-123", **patch_body}
        mock_service.events().patch().execute.return_value = mock_patched

        result = client.patch_event(
            calendar_id="cal-123",
            event_id="event-123",
            body=patch_body,
        )

        assert result["summary"] == "Patched Event"
        mock_service.events().patch.assert_called()

    def test_delete_event(self, client, mock_service):
        """Should delete event."""
        mock_service.events().delete().execute.return_value = None

        # Should not raise
        client.delete_event(calendar_id="cal-123", event_id="event-123")

        mock_service.events().delete.assert_called()

    def test_delete_event_already_deleted(self, client, mock_service):
        """Should handle 404 when deleting already deleted event."""
        mock_service.events().delete().execute.side_effect = make_http_error(404)

        # Should not raise - already deleted is success
        client.delete_event(calendar_id="cal-123", event_id="event-123")

    def test_freebusy_query(self, client, mock_service):
        """Should query free/busy information."""
        mock_response = {
            "calendars": {
                "cal-123": {
                    "busy": [
                        {"start": "2026-01-15T10:00:00Z", "end": "2026-01-15T11:00:00Z"}
                    ]
                }
            }
        }
        mock_service.freebusy().query().execute.return_value = mock_response

        result = client.freebusy_query(
            calendar_ids=["cal-123"],
            time_min="2026-01-15T00:00:00Z",
            time_max="2026-01-16T00:00:00Z",
        )

        assert result == mock_response
        mock_service.freebusy().query.assert_called()

    def test_service_property(self, client, mock_service):
        """Should expose underlying service."""
        assert client.service == mock_service

    def test_http_error_handling(self, client, mock_service):
        """Should convert HttpError to custom exception."""
        mock_service.events().get().execute.side_effect = make_http_error(404)

        with pytest.raises(GoogleCalendarNotFoundError):
            client.get_event(calendar_id="cal-123", event_id="event-123")
