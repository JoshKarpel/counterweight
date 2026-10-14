from __future__ import annotations

from collections.abc import Callable
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

type Getter[T] = Callable[[], T]
type Setter[T] = Callable[[Callable[[T], T] | T], None]
type Setup = Callable[[], Coroutine[None, None, None]]
type Deps = tuple[object, ...] | None


@dataclass(slots=True)
class Ref[T]:
    current: T


@dataclass(frozen=True, slots=True)
class Tick:
    """
    One reading of the app's clock, which [`use_clock`][counterweight.hooks.use_clock] takes for a component
    when it mounts and again on its first render in each new tick.
    Every field comes from the same reading, and every duration is measured on a monotonic clock,
    so changes to the wall clock don't make them jump.
    """

    now: datetime
    """The wall-clock time, in the clock's timezone: the local one unless the app is given another clock."""

    since_start: timedelta
    """How long the app had been running."""

    since_mount: timedelta
    """How long the component had been mounted: zero on the reading taken when it mounts."""
