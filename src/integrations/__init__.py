"""
External service integrations for Family Scheduler.

Provides abstraction layer for calendar storage backends.
"""

from src.integrations.base import CalendarEvent, CalendarRepository

__all__ = ["CalendarEvent", "CalendarRepository"]
