"""
What an autopilot drives an app with: the events and controls it feeds the app,
and the steps that hold it back until real time has passed or the screen shows something.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import assert_never

from counterweight.controls import AnyControl
from counterweight.events import AnyEvent
from counterweight.output import Frame


@dataclass(frozen=True, slots=True)
class Wait:
    """
    Hold the autopilot back for `duration` of real time,
    while the app keeps handling events and rendering, so work like a subprocess can make progress.

    A [`FrozenClock`][counterweight.clock.FrozenClock] runs in real time while the autopilot waits,
    and ends the wait exactly `duration` later, however late the event loop wakes from it.
    The frames the app renders during the wait are timed by when the event loop wakes,
    so a recording with them comes out a little different on every run.

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

    A [`FrozenClock`][counterweight.clock.FrozenClock] runs in real time while the autopilot waits,
    so it moves on by however long the condition took to hold,
    which is different on every run, as is everything the app shows of the time from then on.

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
    """An autopilot partway through its steps, the wait it's in, and how long its waits have taken."""

    steps: Iterator[AutopilotStep]
    waiting: Wait | WaitFor | None = None
    started: float = 0
    """When the wait began, on the event loop's clock."""
    waited: timedelta = timedelta()
    """How long the waits that have ended took: each `Wait` its duration, and each `WaitFor` until its condition held."""

    def next(self, now: float, frame: Callable[[], Frame]) -> AnyEvent | AnyControl | None:
        """
        The next event or control for the app at `now`, on the event loop's clock,
        or `None` while a wait holds the autopilot back or once it has no more steps.
        `frame` gives the frame on screen, for a `WaitFor`'s condition.
        """
        while True:
            match self.waiting:
                case Wait(duration=duration) if now < self.started + duration.total_seconds():
                    return None
                case WaitFor(condition=condition, timeout=timeout) if not condition(frame()):
                    if now >= self.started + timeout.total_seconds():
                        raise AutopilotTimedOut(f"{condition!r} was still false after {timeout}")
                    return None
                case _:
                    self.waited = self.time_waited(now)
                    self.waiting = None

            match step := next(self.steps, None):
                case Wait() | WaitFor():
                    self.waiting = step
                    self.started = now
                case _:
                    return step

    def time_waited(self, now: float) -> timedelta:
        """
        How long the autopilot has spent waiting by `now`, on the event loop's clock,
        counting no more of a `Wait` than its duration, however late the loop wakes from it.
        """
        match self.waiting:
            case Wait(duration=duration):
                return self.waited + min(timedelta(seconds=now - self.started), duration)
            case WaitFor():
                return self.waited + timedelta(seconds=now - self.started)
            case None:
                return self.waited
            case _ as unreachable:
                assert_never(unreachable)

    def until_deadline(self, now: float) -> float | None:
        """How many seconds after `now` the wait the autopilot is in ends, if it's in one."""
        match self.waiting:
            case Wait(duration=limit) | WaitFor(timeout=limit):
                return max(self.started + limit.total_seconds() - now, 0)
            case None:
                return None
            case _ as unreachable:
                assert_never(unreachable)


__all__ = [
    "AutopilotStep",
    "AutopilotTimedOut",
    "Wait",
    "WaitFor",
]
