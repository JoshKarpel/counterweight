"""
What an autopilot drives an app with: the events and controls it feeds the app,
and the steps that hold it back until real time has passed or the screen shows something.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import assert_never
from typing import overload

from counterweight.animation import FRAME_INTERVAL
from counterweight.controls import AdvanceClock
from counterweight.controls import AnyControl
from counterweight.events import AnyEvent
from counterweight.events import KeyPressed
from counterweight.graphemes import graphemes
from counterweight.input_parsing import CONTROL_KEYS
from counterweight.keys import Key
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

TYPED_KEYS: Mapping[str, Key] = {
    **{chr(byte): key for byte, key in CONTROL_KEYS.items()},
    "\x1b": Key.Escape,
    "\n": Key.Enter,
    "\r\n": Key.Enter,
}
"""
The keys `typed` presses for the characters that aren't printed, as a terminal sends them:
each control character's key, Escape for an escape character,
and Enter for a newline, alone or after a carriage return (one grapheme cluster).
"""


@overload
def typed(text: str, pause: None = None) -> list[KeyPressed]: ...


@overload
def typed(text: str, pause: AutopilotStep) -> list[AutopilotStep]: ...


def typed(text: str, pause: AutopilotStep | None = None) -> list[KeyPressed] | list[AutopilotStep]:
    r"""
    The key presses that type `text`, one per grapheme cluster, as Playwright's `keyboard.type` does,
    with a newline (`"\n"` or `"\r\n"`) pressing Enter,
    and any other control character pressing the key a terminal sends it as, such as Tab for a tab.

    Parameters:
        pause: A step to take after each key, such as a [`Wait`][counterweight.autopilot.Wait],
            which gives a program on a pseudo-terminal real time to echo each key before the next arrives,
            or an [`AdvanceClock`][counterweight.controls.AdvanceClock], which paces the typing in a recording
            made on a [`FrozenClock`][counterweight.clock.FrozenClock].
            If `None`, the keys arrive one after another.
    """
    keys = [KeyPressed(key=TYPED_KEYS.get(cluster, cluster)) for cluster in graphemes(text)]
    if pause is None:
        return keys
    return [*(key, pause) for key in keys]


def showing(text: str, timeout: timedelta = timedelta(seconds=30)) -> WaitFor:
    """
    Waits until `text` is on screen, such as a program's prompt, as Playwright's `toContainText` does.

    Raises:
        AutopilotTimedOut: From `app`, if `text` still isn't on screen after `timeout` of real time.
    """
    return WaitFor(lambda frame: text in frame.text(ansi=False), timeout=timeout)


def advance(by: timedelta, step: timedelta = FRAME_INTERVAL) -> list[AdvanceClock]:
    """
    Moves the app's clock on by `by`, `step` at a time, the last step taking whatever is left,
    so each step renders a frame and an animation plays out in a recording rather than jumping to its end,
    as Playwright's `clock.runFor` fires the timers due along the way.
    The default `step` is the interval the animation hooks read the clock at, so each step draws one of their frames.

    Raises:
        ValueError: If `by` is negative, or `step` isn't positive.
    """
    if by < timedelta() or step <= timedelta():
        raise ValueError(
            f"advance needs a duration that isn't negative and a positive step, but got {by!r} and {step!r}"
        )
    count, left = divmod(by, step)
    return [AdvanceClock(by=step)] * count + ([AdvanceClock(by=left)] if left else [])


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
    "advance",
    "showing",
    "typed",
]
