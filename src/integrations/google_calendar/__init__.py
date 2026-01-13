"""
Google Calendar integration for Family Scheduler.

Provides Google Calendar API as a storage backend for events.
"""

from src.integrations.google_calendar.adapter import GoogleCalendarAdapter
from src.integrations.google_calendar.auth import GoogleAuthManager
from src.integrations.google_calendar.client import GoogleCalendarClient
from src.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
    GoogleCalendarConflictError,
    GoogleCalendarError,
    GoogleCalendarNotFoundError,
    GoogleCalendarQuotaError,
    GoogleCalendarRateLimitError,
)
from src.integrations.google_calendar.repository import GoogleCalendarRepository

__all__ = [
    "GoogleCalendarAdapter",
    "GoogleAuthManager",
    "GoogleCalendarClient",
    "GoogleCalendarError",
    "GoogleCalendarAuthError",
    "GoogleCalendarConflictError",
    "GoogleCalendarNotFoundError",
    "GoogleCalendarQuotaError",
    "GoogleCalendarRateLimitError",
    "GoogleCalendarRepository",
]
