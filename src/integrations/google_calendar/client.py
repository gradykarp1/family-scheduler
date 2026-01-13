"""
Google Calendar API client wrapper with retry and error handling.

Provides a clean interface over the Google Calendar API v3.
"""

import logging
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from src.integrations.google_calendar.exceptions import (
    GoogleCalendarError,
    GoogleCalendarAuthError,
    GoogleCalendarQuotaError,
    GoogleCalendarNotFoundError,
    GoogleCalendarConflictError,
    GoogleCalendarRateLimitError,
)

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: Exception) -> bool:
    """Check if an exception should trigger a retry."""
    if isinstance(exception, GoogleCalendarError):
        return exception.retryable
    if isinstance(exception, HttpError):
        return exception.resp.status in (429, 500, 503)
    return False


def _handle_http_error(error: HttpError) -> None:
    """Convert HttpError to appropriate GoogleCalendarError."""
    status = error.resp.status
    message = str(error)

    if status == 401:
        raise GoogleCalendarAuthError(
            "Authentication failed - credentials may be invalid or expired",
            original_error=error,
        )
    elif status == 403:
        if "quota" in message.lower() or "rate limit" in message.lower():
            raise GoogleCalendarQuotaError(
                "API quota exceeded",
                original_error=error,
            )
        raise GoogleCalendarAuthError(
            "Access denied - check calendar sharing permissions",
            original_error=error,
        )
    elif status == 404:
        raise GoogleCalendarNotFoundError(
            "Event or calendar not found",
            original_error=error,
        )
    elif status == 409:
        raise GoogleCalendarConflictError(
            "Event was modified by another process",
            original_error=error,
        )
    elif status == 429:
        raise GoogleCalendarRateLimitError(
            "Rate limit exceeded - too many requests",
            original_error=error,
        )
    else:
        raise GoogleCalendarError(
            f"Google Calendar API error ({status}): {message}",
            original_error=error,
        )


class GoogleCalendarClient:
    """
    Wrapper around Google Calendar API v3.

    Provides:
    - Automatic retry with exponential backoff
    - Consistent error handling
    - Pagination handling for list operations
    """

    def __init__(self, credentials: Credentials):
        """
        Initialize the client.

        Args:
            credentials: Google OAuth2 credentials
        """
        self._service: Resource = build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    @property
    def service(self) -> Resource:
        """Get the underlying Google API service."""
        return self._service

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def list_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str,
        single_events: bool = True,
        max_results: int = 250,
        page_token: Optional[str] = None,
    ) -> dict:
        """
        List events from a calendar.

        Args:
            calendar_id: Calendar to query
            time_min: Lower bound (RFC 3339)
            time_max: Upper bound (RFC 3339)
            single_events: If True, expand recurring events
            max_results: Maximum events per page
            page_token: Token for pagination

        Returns:
            API response with items and nextPageToken
        """
        try:
            request = self._service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=single_events,
                maxResults=max_results,
                pageToken=page_token,
                orderBy="startTime" if single_events else None,
            )
            return request.execute()
        except HttpError as e:
            _handle_http_error(e)

    def list_all_events(
        self,
        calendar_id: str,
        time_min: str,
        time_max: str,
        single_events: bool = True,
    ) -> list[dict]:
        """
        List all events with automatic pagination.

        Args:
            calendar_id: Calendar to query
            time_min: Lower bound (RFC 3339)
            time_max: Upper bound (RFC 3339)
            single_events: If True, expand recurring events

        Returns:
            List of all events in the range
        """
        all_events = []
        page_token = None

        while True:
            response = self.list_events(
                calendar_id=calendar_id,
                time_min=time_min,
                time_max=time_max,
                single_events=single_events,
                page_token=page_token,
            )

            events = response.get("items", [])
            all_events.extend(events)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.debug(f"Listed {len(all_events)} events from {calendar_id}")
        return all_events

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def get_event(self, calendar_id: str, event_id: str) -> dict:
        """
        Get a single event by ID.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event ID

        Returns:
            Event data
        """
        try:
            return self._service.events().get(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
        except HttpError as e:
            _handle_http_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def insert_event(self, calendar_id: str, body: dict) -> dict:
        """
        Create a new event.

        Args:
            calendar_id: Calendar to create event in
            body: Event data in Google Calendar format

        Returns:
            Created event with ID
        """
        try:
            result = self._service.events().insert(
                calendarId=calendar_id,
                body=body,
            ).execute()
            logger.info(f"Created event {result.get('id')} in {calendar_id}")
            return result
        except HttpError as e:
            _handle_http_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def update_event(self, calendar_id: str, event_id: str, body: dict) -> dict:
        """
        Update an existing event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to update
            body: Updated event data

        Returns:
            Updated event
        """
        try:
            result = self._service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=body,
            ).execute()
            logger.info(f"Updated event {event_id} in {calendar_id}")
            return result
        except HttpError as e:
            _handle_http_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def patch_event(self, calendar_id: str, event_id: str, body: dict) -> dict:
        """
        Patch an existing event (partial update).

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to update
            body: Fields to update

        Returns:
            Updated event
        """
        try:
            result = self._service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=body,
            ).execute()
            logger.info(f"Patched event {event_id} in {calendar_id}")
            return result
        except HttpError as e:
            _handle_http_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def delete_event(self, calendar_id: str, event_id: str) -> None:
        """
        Delete an event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to delete
        """
        try:
            self._service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
            ).execute()
            logger.info(f"Deleted event {event_id} from {calendar_id}")
        except HttpError as e:
            if e.resp.status == 404:
                # Already deleted - consider success
                logger.warning(f"Event {event_id} already deleted")
                return
            _handle_http_error(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def freebusy_query(
        self,
        calendar_ids: list[str],
        time_min: str,
        time_max: str,
    ) -> dict:
        """
        Query free/busy information.

        Args:
            calendar_ids: Calendars to query
            time_min: Lower bound (RFC 3339)
            time_max: Upper bound (RFC 3339)

        Returns:
            Free/busy data for each calendar
        """
        try:
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": cal_id} for cal_id in calendar_ids],
            }
            return self._service.freebusy().query(body=body).execute()
        except HttpError as e:
            _handle_http_error(e)
