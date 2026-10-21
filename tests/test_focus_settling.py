"""
What the render that settles focus reads, when it re-runs the components that gained and lost focus before painting:
the same clock reading, layouts and purity check as the render that moved focus.
"""

from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from itertools import count

import pytest

from counterweight import app
from counterweight._output import Frame
from counterweight.clock import FrozenClock
from counterweight.components import Component
from counterweight.components import ImpureComponent
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.styles.utilities import col
from counterweight.styles.utilities import size

TOGGLE = KeyPressed(key="t")
NOON = datetime(2024, 1, 2, 12, tzinfo=UTC)


def toggled(children: Callable[[bool], tuple[Component, ...]]) -> Component:
    """A root that renders `children(flag)`, with a flag that starts `False` and flips on `TOGGLE`."""

    @component
    def root() -> Div:
        flag, set_flag = use_state(False)

        def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
            set_flag(not flag)
            return ()

        return Div(style=col, on_input=on_input, children=children(flag))

    return root()


async def screenshot_after_toggle(root: Component, check_purity: bool = False, at: datetime = NOON) -> str:
    """The screen's text after `TOGGLE`, read by a clock frozen `at`, with no render after the one `TOGGLE` causes."""
    frames: list[Frame] = []
    await app(
        root,
        headless=True,
        dimensions=(9, 1),
        autopilot=[TOGGLE, Screenshot(handler=frames.append), Quit()],
        check_purity=check_purity,
        clock=FrozenClock(at),
    )
    (frame,) = frames
    return frame.text(ansi=False)


@component
def reads_the_clock() -> Text:
    tick = use_clock(timedelta(hours=1))
    return Text(content=tick.now.strftime("%H:%M:%S"))


@component
def shows_the_clock_when_focused() -> Div:
    focus = use_focus(auto_focus=True)
    return Div(children=(reads_the_clock(),) if focus.is_focused else ())


async def test_a_component_mounted_by_the_render_that_settles_focus_reads_the_clock_reading_of_that_frame() -> None:
    root = toggled(lambda is_mounted: (shows_the_clock_when_focused(),) if is_mounted else ())

    assert await screenshot_after_toggle(root, at=datetime(2025, 3, 4, 5, 6, 7, tzinfo=UTC)) == "05:06:07 "


@component
def measured(is_focusable: bool) -> Text:
    focus = use_focus(auto_focus=True, is_focusable=is_focusable)
    rects = use_rects()
    return Text(content=f"{'on' if focus.is_focused else 'off'} {rects.border.width}", style=size(7, 1))


async def test_a_component_that_loses_focus_in_the_render_that_settles_it_reads_its_rects() -> None:
    root = toggled(lambda is_disabled: (measured(is_focusable=not is_disabled),))

    assert await screenshot_after_toggle(root) == "off 7    "


async def test_check_purity_checks_the_components_the_render_that_settles_focus_runs() -> None:
    renders = count()

    @component
    def impure_when_focused() -> Text:
        focus = use_focus(auto_focus=True)
        return Text(content=str(next(renders)) if focus.is_focused else "unfocused")

    root = toggled(lambda is_mounted: (impure_when_focused(),) if is_mounted else ())

    with pytest.raises(ImpureComponent, match=r"^test_check_purity_checks_.*\.impure_when_focused returned "):
        await screenshot_after_toggle(root, check_purity=True)
