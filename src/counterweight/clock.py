"""
Where an app gets the time: the `Clock` it reads once per frame, and the `Instant`s it reads from it.
`use_clock` hands components readings of those instants, and the render loop sleeps until the next one is due.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from time import monotonic
from typing import assert_never

# Naive on purpose: ticks count the wall clock's own time, whatever its zone.
EPOCH = datetime(1970, 1, 1)  # noqa: DTZ001


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


@dataclass(frozen=True, slots=True)
class SystemClock:
    """
    The system's clock, which an app reads unless it's given another.
    Time passes on it as it really does,
    and [`AdvanceClock`][counterweight.controls.AdvanceClock] moves it on further.
    """

    timezone: tzinfo = UTC
    """
    The timezone the clock reads the wall-clock time in,
    such as `ZoneInfo("America/New_York")`, which ticks follow too.
    """


@dataclass(frozen=True, slots=True)
class FrozenClock:
    """
    A clock that starts at `start` and moves only when an autopilot moves it,
    so tests, screenshots and recordings don't depend on when they run or how long they take.
    [`AdvanceClock`][counterweight.controls.AdvanceClock] moves it on at once,
    and [`Wait`][counterweight.autopilot.Wait] and [`WaitFor`][counterweight.autopilot.WaitFor]
    let it run in real time while the autopilot waits.

    Raises:
        ValueError: If `start` has no timezone.
    """

    start: datetime
    """When the clock starts, in the timezone it reads the wall-clock time in."""

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError(f"A frozen clock starts at a time with a timezone, not the naive {self.start!r}")


type Clock = SystemClock | FrozenClock
"""Where an app reads the time."""


def reading(clock: Clock, waited: timedelta) -> Instant:
    """
    The time on `clock` now, where an autopilot has spent `waited` of real time waiting:
    the system's clock has passed that time already, and it's the only time a frozen clock has passed.
    """
    match clock:
        case SystemClock(timezone=timezone):
            return Instant(wall=datetime.now(timezone), monotonic=timedelta(seconds=monotonic()))
        case FrozenClock(start=start):
            return Instant(wall=start + waited, monotonic=waited)
        case _ as unreachable:
            assert_never(unreachable)


def tick_index(wall: datetime, interval: timedelta) -> int:
    """
    Which `interval`-long tick `wall` falls in, counted on its own wall clock,
    so ticks start at whole multiples of `interval` past midnight wherever `interval` divides a day.
    """
    return (wall.replace(tzinfo=None) - EPOCH) // interval


def until_next_tick(wall: datetime, interval: timedelta) -> timedelta:
    """How long after `wall` the next `interval`-long tick starts."""
    return EPOCH + (tick_index(wall, interval) + 1) * interval - wall.replace(tzinfo=None)
