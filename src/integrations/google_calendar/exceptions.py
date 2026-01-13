"""
Custom exceptions for Google Calendar operations.

Provides structured error handling with retryable flags.
"""


class GoogleCalendarError(Exception):
    """Base exception for Google Calendar operations."""

    retryable: bool = False

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class GoogleCalendarAuthError(GoogleCalendarError):
    """
    Authentication or authorization failure.

    Causes:
    - Invalid or expired credentials
    - Insufficient scopes
    - Service account not authorized for calendar
    """

    retryable = False


class GoogleCalendarQuotaError(GoogleCalendarError):
    """
    API quota exceeded.

    Google Calendar API has quotas:
    - 1,000,000 queries/day
    - 180 queries/minute per user

    Retryable after backoff.
    """

    retryable = True


class GoogleCalendarNotFoundError(GoogleCalendarError):
    """
    Event or calendar not found.

    Causes:
    - Event was deleted
    - Calendar ID is invalid
    - Event ID is invalid
    """

    retryable = False


class GoogleCalendarConflictError(GoogleCalendarError):
    """
    Event update conflict.

    Causes:
    - Stale etag (event was modified concurrently)
    - Version mismatch

    Retryable after re-fetching the event.
    """

    retryable = True


class GoogleCalendarRateLimitError(GoogleCalendarError):
    """
    Rate limit hit (429 response).

    Retryable after exponential backoff.
    """

    retryable = True


class GoogleCalendarValidationError(GoogleCalendarError):
    """
    Invalid event data.

    Causes:
    - Invalid datetime format
    - Missing required fields
    - Invalid recurrence rule
    """

    retryable = False
