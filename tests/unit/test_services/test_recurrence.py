"""
Unit tests for the recurrence service.

Tests RRULE parsing and expansion functionality.
"""

import pytest
from datetime import datetime, timedelta

from src.services.recurrence import (
    RecurrenceInstance,
    parse_rrule,
    expand_recurrence,
    format_recurrence_id,
    parse_recurrence_id,
    get_next_occurrence,
    validate_rrule,
    count_instances_in_range,
)


class TestParseRrule:
    """Test parse_rrule function."""

    def test_parse_weekly_rule(self):
        """Test parsing a weekly recurrence rule."""
        dtstart = datetime(2026, 1, 5, 10, 0, 0)  # Monday
        rule = parse_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR", dtstart)

        assert rule is not None

    def test_parse_daily_rule(self):
        """Test parsing a daily recurrence rule."""
        dtstart = datetime(2026, 1, 1, 9, 0, 0)
        rule = parse_rrule("FREQ=DAILY", dtstart)

        assert rule is not None

    def test_parse_monthly_rule(self):
        """Test parsing a monthly recurrence rule."""
        dtstart = datetime(2026, 1, 15, 14, 0, 0)
        rule = parse_rrule("FREQ=MONTHLY;BYMONTHDAY=15", dtstart)

        assert rule is not None

    def test_parse_with_count(self):
        """Test parsing a rule with COUNT limit."""
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        rule = parse_rrule("FREQ=DAILY;COUNT=5", dtstart)

        assert rule is not None

    def test_parse_with_until(self):
        """Test parsing a rule with UNTIL limit."""
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        # Use simpler UNTIL format that dateutil handles better
        rule = parse_rrule("FREQ=WEEKLY;UNTIL=20260201", dtstart)

        assert rule is not None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        rule = parse_rrule("", datetime(2026, 1, 1))
        assert rule is None

    def test_parse_none(self):
        """Test parsing None returns None."""
        rule = parse_rrule(None, datetime(2026, 1, 1))
        assert rule is None


class TestExpandRecurrence:
    """Test expand_recurrence function."""

    def test_expand_daily_rule(self):
        """Test expanding a daily recurrence."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        duration = timedelta(hours=1)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 1, 5, 23, 59, 59)

        instances = expand_recurrence(rrule, dtstart, duration, window_start, window_end)

        assert len(instances) == 5
        assert all(isinstance(i, RecurrenceInstance) for i in instances)
        assert instances[0].instance_start == datetime(2026, 1, 1, 10, 0, 0)
        assert instances[0].instance_end == datetime(2026, 1, 1, 11, 0, 0)

    def test_expand_weekly_rule(self):
        """Test expanding a weekly recurrence on specific days."""
        rrule = "FREQ=WEEKLY;BYDAY=MO,WE,FR"
        dtstart = datetime(2026, 1, 5, 9, 0, 0)  # Monday
        duration = timedelta(hours=2)
        window_start = datetime(2026, 1, 5, 0, 0, 0)
        window_end = datetime(2026, 1, 12, 23, 59, 59)  # One week

        instances = expand_recurrence(rrule, dtstart, duration, window_start, window_end)

        # Should have Mon, Wed, Fri of both weeks
        assert len(instances) >= 3

    def test_expand_with_max_instances(self):
        """Test that max_instances limits output."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        duration = timedelta(hours=1)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 12, 31, 23, 59, 59)  # Full year

        instances = expand_recurrence(
            rrule, dtstart, duration, window_start, window_end, max_instances=10
        )

        assert len(instances) == 10

    def test_expand_empty_rrule(self):
        """Test that empty rrule returns empty list."""
        instances = expand_recurrence(
            "",
            datetime(2026, 1, 1),
            timedelta(hours=1),
            datetime(2026, 1, 1),
            datetime(2026, 1, 31),
        )
        assert instances == []

    def test_expand_no_instances_in_window(self):
        """Test when no instances fall within window."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 2, 1, 10, 0, 0)  # Starts in February
        duration = timedelta(hours=1)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 1, 15, 0, 0, 0)  # January only

        instances = expand_recurrence(rrule, dtstart, duration, window_start, window_end)

        assert len(instances) == 0

    def test_instance_has_recurrence_id(self):
        """Test that instances have properly formatted recurrence IDs."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 14, 30, 0)
        duration = timedelta(hours=1)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 1, 2, 0, 0, 0)

        instances = expand_recurrence(rrule, dtstart, duration, window_start, window_end)

        assert instances[0].recurrence_id == "20260101T143000"


class TestFormatRecurrenceId:
    """Test format_recurrence_id function."""

    def test_format_datetime(self):
        """Test formatting a datetime as recurrence ID."""
        dt = datetime(2026, 3, 15, 14, 30, 45)
        result = format_recurrence_id(dt)
        assert result == "20260315T143045"

    def test_format_midnight(self):
        """Test formatting midnight."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = format_recurrence_id(dt)
        assert result == "20260101T000000"


class TestParseRecurrenceId:
    """Test parse_recurrence_id function."""

    def test_parse_valid_id(self):
        """Test parsing a valid recurrence ID."""
        result = parse_recurrence_id("20260315T143045")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45

    def test_parse_invalid_id(self):
        """Test parsing an invalid ID returns None."""
        result = parse_recurrence_id("invalid")
        assert result is None

    def test_parse_empty_id(self):
        """Test parsing empty string returns None."""
        result = parse_recurrence_id("")
        assert result is None

    def test_roundtrip(self):
        """Test format and parse roundtrip."""
        original = datetime(2026, 6, 15, 9, 45, 30)
        formatted = format_recurrence_id(original)
        parsed = parse_recurrence_id(formatted)

        assert parsed is not None
        assert parsed.year == original.year
        assert parsed.month == original.month
        assert parsed.day == original.day
        assert parsed.hour == original.hour
        assert parsed.minute == original.minute
        assert parsed.second == original.second


class TestGetNextOccurrence:
    """Test get_next_occurrence function."""

    def test_get_next_daily(self):
        """Test getting next occurrence of daily event."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        after = datetime(2026, 1, 5, 12, 0, 0)

        result = get_next_occurrence(rrule, dtstart, after)

        assert result is not None
        assert result == datetime(2026, 1, 6, 10, 0, 0)

    def test_get_next_weekly(self):
        """Test getting next occurrence of weekly event."""
        rrule = "FREQ=WEEKLY;BYDAY=MO"
        dtstart = datetime(2026, 1, 5, 9, 0, 0)  # Monday
        after = datetime(2026, 1, 6, 0, 0, 0)  # Tuesday

        result = get_next_occurrence(rrule, dtstart, after)

        assert result is not None
        assert result.weekday() == 0  # Monday

    def test_get_next_with_empty_rrule(self):
        """Test with empty rrule returns None."""
        result = get_next_occurrence("", datetime(2026, 1, 1))
        assert result is None


class TestValidateRrule:
    """Test validate_rrule function."""

    def test_valid_daily_rule(self):
        """Test valid daily rule."""
        is_valid, error = validate_rrule("FREQ=DAILY")
        assert is_valid is True
        assert error is None

    def test_valid_weekly_rule(self):
        """Test valid weekly rule with days."""
        is_valid, error = validate_rrule("FREQ=WEEKLY;BYDAY=MO,WE,FR")
        assert is_valid is True
        assert error is None

    def test_valid_monthly_rule(self):
        """Test valid monthly rule."""
        is_valid, error = validate_rrule("FREQ=MONTHLY;BYMONTHDAY=1")
        assert is_valid is True
        assert error is None

    def test_invalid_missing_freq(self):
        """Test rule without FREQ is invalid."""
        is_valid, error = validate_rrule("BYDAY=MO")
        assert is_valid is False
        assert "FREQ" in error

    def test_invalid_empty_string(self):
        """Test empty string is invalid."""
        is_valid, error = validate_rrule("")
        assert is_valid is False
        assert error is not None

    def test_invalid_blank_string(self):
        """Test blank string is invalid."""
        is_valid, error = validate_rrule("   ")
        assert is_valid is False
        assert error is not None


class TestCountInstancesInRange:
    """Test count_instances_in_range function."""

    def test_count_daily_occurrences(self):
        """Test counting daily occurrences."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 1, 10, 23, 59, 59)

        count = count_instances_in_range(rrule, dtstart, window_start, window_end)

        assert count == 10

    def test_count_with_max(self):
        """Test counting respects max_count."""
        rrule = "FREQ=DAILY"
        dtstart = datetime(2026, 1, 1, 10, 0, 0)
        window_start = datetime(2026, 1, 1, 0, 0, 0)
        window_end = datetime(2026, 12, 31, 23, 59, 59)

        count = count_instances_in_range(
            rrule, dtstart, window_start, window_end, max_count=50
        )

        assert count == 50

    def test_count_empty_rrule(self):
        """Test counting with empty rrule returns 0."""
        count = count_instances_in_range(
            "", datetime(2026, 1, 1), datetime(2026, 1, 1), datetime(2026, 1, 31)
        )
        assert count == 0
