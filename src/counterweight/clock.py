"""
Where an app gets the time: the `Clock` it reads once per frame, and the `Instant`s it reads from it.
`use_clock` hands components readings of those instants, and the render loop sleeps until the next one is due.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic

LOCAL_EPOCH = datetime(1970, 1, 1)


@dataclass(frozen=True, slots=True)
class Instant:
    """One reading of a clock: the wall-clock time, and a monotonic time read along with it."""

    wall: datetime
    monotonic: timedelta
    """Unaffected by changes to the wall clock. Only the difference between two instants from one clock means anything."""

    def __add__(self, other: timedelta) -> Instant:
        return Instant(wall=self.wall + other, monotonic=self.monotonic + other)


# The instant a render reads when nothing tells it the time, as in a test that doesn't read the clock.
BEGINNING = Instant(wall=datetime(1970, 1, 1, tzinfo=UTC), monotonic=timedelta())

# Where an app reads the time: `system_clock` unless told otherwise.
type Clock = Callable[[], Instant]


def system_clock() -> Instant:
    """The system's clock, with the wall-clock time in the local timezone."""
    return Instant(wall=datetime.now().astimezone(), monotonic=timedelta(seconds=monotonic()))


def frozen_clock(wall: datetime) -> Clock:
    """
    A clock that always reads `wall`, for tests and screenshots that mustn't depend on when they run.
    Advance it with the [`AdvanceClock`][counterweight.controls.AdvanceClock] control.
    """
    instant = Instant(wall=wall, monotonic=timedelta())
    return lambda: instant


def tick_index(wall: datetime, interval: timedelta) -> int:
    """
    Which `interval`-long tick `wall` falls in, counted on its own wall clock,
    so ticks start at whole multiples of `interval` past midnight wherever `interval` divides a day.
    """
    return (wall.replace(tzinfo=None) - LOCAL_EPOCH) // interval


def until_next_tick(wall: datetime, interval: timedelta) -> timedelta:
    """How long after `wall` the next `interval`-long tick starts."""
    return LOCAL_EPOCH + (tick_index(wall, interval) + 1) * interval - wall.replace(tzinfo=None)
