from __future__ import annotations

from collections.abc import Callable
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

type Getter[T] = Callable[[], T]
"""A function that computes a value, such as the initial state `use_state` computes only on the first render."""

type Setter[T] = Callable[[Callable[[T], T] | T], None]
"""
What `use_state` returns to set its state: given a value, the next state,
or given a function, the next state computed from the latest one.
"""

type Setup = Callable[[], Coroutine[None, None, None]]
"""What `use_effect` runs: an async function the app runs as a task, and cancels to clean it up."""

type Deps = tuple[object, ...] | None
"""
The values an effect depends on, which `use_effect` compares with `==` to the last render's
to decide whether to run it again, or `None` to run it again after every render of its component.
"""


@dataclass(slots=True)
class Ref[T]:
    """
    A mutable box that keeps a value across renders, which `use_ref` returns, the same box on every render.
    Changing what it holds doesn't render the component again.
    """

    current: T
    """The value the box holds."""


@dataclass(frozen=True, slots=True)
class Tick:
    """
    One reading of the app's clock, which [`use_clock`][counterweight.hooks.use_clock] takes for a component
    when it mounts and again on its first render in each new tick.
    Every field comes from the same reading, and every duration is measured on a monotonic clock,
    so changes to the wall clock don't make them jump.
    """

    now: datetime
    """The wall-clock time, in the clock's timezone: UTC unless the app's clock is given another."""

    since_start: timedelta
    """How long the app had been running."""

    since_mount: timedelta
    """How long the component had been mounted: zero on the reading taken when it mounts."""
