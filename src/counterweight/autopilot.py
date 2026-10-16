"""
What an autopilot drives an app with: the events and controls it feeds the app,
and the steps that hold it back until real time has passed or the screen shows something.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from counterweight.controls import AnyControl
from counterweight.events import AnyEvent
from counterweight.output import Frame


@dataclass(frozen=True, slots=True)
class Wait:
    """
    Hold the autopilot back for `duration` of real time,
    while the app keeps handling events and rendering, so work like a subprocess can make progress.

    It's measured on the event loop's clock, not the app's:
    with a [`frozen_clock`][counterweight.clock.frozen_clock] the app's time stands still while it waits,
    and [`AdvanceClock`][counterweight.controls.AdvanceClock] is what moves it.
    To wait for work to finish, prefer [`WaitFor`][counterweight.autopilot.WaitFor],
    which doesn't have to guess how long the work takes.
    """

    duration: timedelta


@dataclass(frozen=True, slots=True)
class WaitFor:
    """
    Hold the autopilot back until `condition` is true of the frame on screen,
    checked after each render, while the app keeps handling events and rendering,
    as [Playwright's assertions](https://playwright.dev/docs/test-assertions) wait for the page.

    The condition receives the whole screen as a [`Frame`][counterweight.output.Frame],
    so it can look for text with `frame.text(ansi=False)`.

    Raises:
        AutopilotTimedOut: From `app`, if the condition is still false after `timeout` of real time.
    """

    condition: Callable[[Frame], bool]
    timeout: timedelta


class AutopilotTimedOut(Exception):
    """A [`WaitFor`][counterweight.autopilot.WaitFor]'s condition was still false when its timeout passed."""


AutopilotStep = AnyEvent | AnyControl | Wait | WaitFor
"""What an autopilot feeds an app: events, controls, and the steps that wait."""


@dataclass(slots=True)
class Autopilot:
    """An autopilot partway through its steps, and the wait it's in, which ends (or times out) at `deadline`."""

    steps: Iterator[AutopilotStep]
    waiting: Wait | WaitFor | None = None
    deadline: float = 0
    """When the wait ends, on the event loop's clock."""

    def next(self, now: float, frame: Callable[[], Frame]) -> AnyEvent | AnyControl | None:
        """
        The next event or control for the app at `now`, on the event loop's clock,
        or `None` while a wait holds the autopilot back or once it has no more steps.
        `frame` gives the frame on screen, for a `WaitFor`'s condition.
        """
        while True:
            match self.waiting:
                case Wait() if now < self.deadline:
                    return None
                case WaitFor(condition=condition, timeout=timeout) if not condition(frame()):
                    if now >= self.deadline:
                        raise AutopilotTimedOut(f"{condition!r} was still false after {timeout}")
                    return None
                case _:
                    self.waiting = None

            match step := next(self.steps, None):
                case Wait(duration=duration) | WaitFor(timeout=duration):
                    self.waiting = step
                    self.deadline = now + duration.total_seconds()
                case _:
                    return step

    def until_deadline(self, now: float) -> float | None:
        """How many seconds after `now` the wait the autopilot is in ends, if it's in one."""
        return None if self.waiting is None else max(self.deadline - now, 0)


__all__ = [
    "AutopilotStep",
    "AutopilotTimedOut",
    "Wait",
    "WaitFor",
]
