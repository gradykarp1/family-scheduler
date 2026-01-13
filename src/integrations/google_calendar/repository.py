"""
Google Calendar Repository implementation.

Implements CalendarRepository protocol using Google Calendar API.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Optional, Sequence

from src.integrations.base import (
    CalendarEvent,
    CalendarRepository,
    CreateEventRequest,
    FreeBusySlot,
)
from src.integrations.google_calendar.adapter import GoogleCalendarAdapter
from src.integrations.google_calendar.auth import GoogleAuthManager
from src.integrations.google_calendar.client import GoogleCalendarClient
from src.integrations.google_calendar.exceptions import (
    GoogleCalendarNotFoundError,
)

logger = logging.getLogger(__name__)


def _format_rfc3339(dt: datetime) -> str:
    """Format datetime to RFC 3339 for Google API."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class GoogleCalendarRepository(CalendarRepository):
    """
    CalendarRepository implementation using Google Calendar API.

    Uses service account authentication for server-to-server access.
    The Google API client is synchronous, so we run operations in a
    thread pool for async compatibility.
    """

    def __init__(
        self,
        auth_manager: GoogleAuthManager,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        """
        Initialize the repository.

        Args:
            auth_manager: Authentication manager for credentials
            executor: Thread pool for running sync API calls (creates default if None)
        """
        self._auth_manager = auth_manager
        self._executor = executor or ThreadPoolExecutor(max_workers=4)
        self._client: Optional[GoogleCalendarClient] = None
        self._adapter = GoogleCalendarAdapter()

    @property
    def client(self) -> GoogleCalendarClient:
        """Get or create the API client."""
        if self._client is None:
            credentials = self._auth_manager.get_credentials()
            self._client = GoogleCalendarClient(credentials)
        return self._client

    async def _run_in_executor(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            partial(func, *args, **kwargs),
        )

    async def get_events_in_range(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        include_recurring: bool = True,
    ) -> Sequence[CalendarEvent]:
        """
        Get events within a time range from Google Calendar.

        Args:
            calendar_id: Google Calendar ID
            start: Range start (inclusive)
            end: Range end (exclusive)
            include_recurring: Whether to expand recurring events into instances

        Returns:
            Sequence of events in the range
        """
        time_min = _format_rfc3339(start)
        time_max = _format_rfc3339(end)

        google_events = await self._run_in_executor(
            self.client.list_all_events,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            single_events=include_recurring,
        )

        events = [
            self._adapter.from_google_event(event, calendar_id)
            for event in google_events
        ]

        logger.debug(
            f"Retrieved {len(events)} events from {calendar_id} "
            f"between {start} and {end}"
        )
        return events

    async def get_event_by_id(
        self,
        calendar_id: str,
        event_id: str,
    ) -> Optional[CalendarEvent]:
        """
        Get a single event by ID from Google Calendar.

        Args:
            calendar_id: Google Calendar ID
            event_id: Event ID

        Returns:
            Event or None if not found
        """
        try:
            google_event = await self._run_in_executor(
                self.client.get_event,
                calendar_id=calendar_id,
                event_id=event_id,
            )
            return self._adapter.from_google_event(google_event, calendar_id)
        except GoogleCalendarNotFoundError:
            return None

    async def create_event(
        self,
        calendar_id: str,
        event: CreateEventRequest,
    ) -> CalendarEvent:
        """
        Create a new event in Google Calendar.

        Args:
            calendar_id: Google Calendar ID
            event: Event data

        Returns:
            Created event with assigned ID
        """
        google_event_body = self._adapter.to_google_event(event)

        google_event = await self._run_in_executor(
            self.client.insert_event,
            calendar_id=calendar_id,
            body=google_event_body,
        )

        created_event = self._adapter.from_google_event(google_event, calendar_id)
        logger.info(f"Created event '{event.title}' with ID {created_event.id}")
        return created_event

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: dict,
    ) -> CalendarEvent:
        """
        Update an existing event in Google Calendar.

        Uses PATCH for partial updates.

        Args:
            calendar_id: Google Calendar ID
            event_id: Event to update
            updates: Fields to update

        Returns:
            Updated event
        """
        google_updates = self._adapter.to_update_body(updates)

        google_event = await self._run_in_executor(
            self.client.patch_event,
            calendar_id=calendar_id,
            event_id=event_id,
            body=google_updates,
        )

        updated_event = self._adapter.from_google_event(google_event, calendar_id)
        logger.info(f"Updated event {event_id}: {list(updates.keys())}")
        return updated_event

    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """
        Delete an event from Google Calendar.

        Args:
            calendar_id: Google Calendar ID
            event_id: Event to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            await self._run_in_executor(
                self.client.delete_event,
                calendar_id=calendar_id,
                event_id=event_id,
            )
            logger.info(f"Deleted event {event_id} from {calendar_id}")
            return True
        except GoogleCalendarNotFoundError:
            logger.warning(f"Event {event_id} not found for deletion")
            return False

    async def find_free_busy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, list[FreeBusySlot]]:
        """
        Query free/busy information from Google Calendar.

        Args:
            calendar_ids: Calendar IDs to query
            start: Range start
            end: Range end

        Returns:
            Dict mapping calendar_id to list of busy slots
        """
        time_min = _format_rfc3339(start)
        time_max = _format_rfc3339(end)

        response = await self._run_in_executor(
            self.client.freebusy_query,
            calendar_ids=calendar_ids,
            time_min=time_min,
            time_max=time_max,
        )

        return self._adapter.parse_freebusy_response(response)

    async def close(self):
        """Clean up resources."""
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
