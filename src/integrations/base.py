"""
Calendar repository protocol and base types.

Defines the interface for calendar storage backends (Google Calendar, local database, etc.).
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol, Sequence


@dataclass
class CalendarEvent:
    """
    Normalized event representation across calendar providers.

    This is the common format used by the service layer, mapped from
    provider-specific formats by adapters.
    """

    id: str
    calendar_id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    all_day: bool = False
    location: Optional[str] = None
    attendees: list[str] = field(default_factory=list)
    recurrence_rule: Optional[str] = None
    status: str = "confirmed"
    metadata: dict = field(default_factory=dict)

    @property
    def duration_minutes(self) -> int:
        """Calculate event duration in minutes."""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)


@dataclass
class FreeBusySlot:
    """Represents a busy time slot."""

    start: datetime
    end: datetime


@dataclass
class CreateEventRequest:
    """
    Request to create a new event.

    Used as input to CalendarRepository.create_event().
    """

    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    all_day: bool = False
    location: Optional[str] = None
    attendees: list[str] = field(default_factory=list)
    recurrence_rule: Optional[str] = None
    priority: str = "medium"
    flexibility: str = "fixed"
    created_by: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class CalendarRepository(Protocol):
    """
    Protocol for calendar storage backends.

    Implementations:
    - GoogleCalendarRepository: Uses Google Calendar API
    - SQLAlchemyCalendarRepository: Uses local database (fallback)

    All methods are async for compatibility with external API calls.
    """

    @abstractmethod
    async def get_events_in_range(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        include_recurring: bool = True,
    ) -> Sequence[CalendarEvent]:
        """
        Get events within a time range.

        Args:
            calendar_id: Calendar to query
            start: Range start (inclusive)
            end: Range end (exclusive)
            include_recurring: Whether to expand recurring events

        Returns:
            Sequence of events in the range
        """
        ...

    @abstractmethod
    async def get_event_by_id(
        self,
        calendar_id: str,
        event_id: str,
    ) -> Optional[CalendarEvent]:
        """
        Get a single event by ID.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event ID

        Returns:
            Event or None if not found
        """
        ...

    @abstractmethod
    async def create_event(
        self,
        calendar_id: str,
        event: CreateEventRequest,
    ) -> CalendarEvent:
        """
        Create a new event.

        Args:
            calendar_id: Calendar to create event in
            event: Event data

        Returns:
            Created event with assigned ID
        """
        ...

    @abstractmethod
    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: dict,
    ) -> CalendarEvent:
        """
        Update an existing event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to update
            updates: Fields to update

        Returns:
            Updated event
        """
        ...

    @abstractmethod
    async def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> bool:
        """
        Delete an event.

        Args:
            calendar_id: Calendar containing the event
            event_id: Event to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def find_free_busy(
        self,
        calendar_ids: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, list[FreeBusySlot]]:
        """
        Query free/busy information for calendars.

        Args:
            calendar_ids: Calendars to query
            start: Range start
            end: Range end

        Returns:
            Dict mapping calendar_id to list of busy slots
        """
        ...
