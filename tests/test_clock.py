from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo

import pytest

from counterweight.clock import FrozenClock
from counterweight.clock import Instant
from counterweight.clock import SystemClock
from counterweight.clock import reading

START = datetime(2026, 3, 14, 15, 9, 26, tzinfo=timezone(timedelta(hours=-4)))


def test_the_system_clock_reads_utc_unless_given_a_timezone() -> None:
    assert reading(SystemClock(), timedelta()).wall.tzinfo is UTC


def test_the_system_clock_reads_the_timezone_it_is_given() -> None:
    zone = ZoneInfo("Asia/Kolkata")

    assert reading(SystemClock(timezone=zone), timedelta()).wall.tzinfo is zone


def test_the_system_clock_has_passed_the_time_waited_already() -> None:
    before = datetime.now(UTC)

    now = reading(SystemClock(), timedelta(hours=3))

    assert before <= now.wall <= datetime.now(UTC)


def test_a_frozen_clock_reads_its_start_until_time_is_waited() -> None:
    assert reading(FrozenClock(START), timedelta()) == Instant(wall=START, monotonic=timedelta())


def test_a_frozen_clock_has_passed_only_the_time_waited() -> None:
    waited = timedelta(seconds=2, milliseconds=5)

    assert reading(FrozenClock(START), waited) == Instant(wall=START + waited, monotonic=waited)


def test_a_frozen_clock_needs_a_start_with_a_timezone() -> None:
    with pytest.raises(ValueError, match="naive"):
        FrozenClock(datetime(2026, 3, 14))  # noqa: DTZ001
