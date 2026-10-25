import json
import logging
from pathlib import Path

import pytest

from counterweight import app
from counterweight._app import SETTLING_PASSES
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import ScrollBy
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.focus import UnsettledFocus
from counterweight.hooks import UnsettledMeasurements
from counterweight.hooks import use_focus
from counterweight.hooks import use_rects
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.utilities import col
from counterweight.styles.utilities import display_none
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import size

HANDLE = ElementHandle()
SIZED = ElementHandle()
FIELD = FocusHandle()
WIDTH, HEIGHT = 8, 3


async def painted(tmp_path: Path, root: Component, autopilot: list[AutopilotStep]) -> list[list[str]]:
    """The lines of every frame `root` paints, played back from a recording of it."""
    path = tmp_path / "frames.cast"
    await app(
        root, headless=True, dimensions=(WIDTH, HEIGHT), autopilot=[*autopilot, Quit()], recording=Recording(path)
    )

    frames = []
    with Emulator(WIDTH, HEIGHT, on_reply=lambda reply: None) as emulator:
        for line in path.read_text().splitlines()[1:]:
            _, code, data = json.loads(line)
            if code == "o":
                emulator.feed(data.encode())
                frames.append(["".join(cell.grapheme for cell in row).rstrip() for row in emulator.snapshot().lines])
    # The first output is the preamble that sets the terminal up, before any frame.
    return frames[1:]


@component
def width_of_handle() -> Text:
    return Text(content=str(use_rects(HANDLE).border.width))


async def test_a_component_reading_a_rect_that_moved_is_drawn_from_it_in_the_frame_that_moved_it(
    tmp_path: Path,
) -> None:
    @component
    def root() -> Div:
        width, set_width = use_state(3)

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_width(5)

        return Div(
            style=col,
            on_input=on_input,
            children=(
                Div(handle=HANDLE, style=size(width, 1), children=(Text(content="#" * width),)),
                width_of_handle(),
            ),
        )

    assert await painted(tmp_path, root(), [KeyPressed(key="w")]) == [["###", "3", ""], ["#####", "5", ""]]


async def test_a_component_reading_a_scroll_that_moved_is_drawn_from_it_in_the_frame_that_moved_it(
    tmp_path: Path,
) -> None:
    @component
    def offset() -> Text:
        return Text(content=f"at {use_scroll(HANDLE).offset.y}")

    @component
    def root() -> Div:
        lines = tuple(Text(content=f"line {n}") for n in range(5))
        return Div(
            style=col,
            children=(offset(), Div(handle=HANDLE, style=col | size(8, 2) | overflow_y_scroll, children=lines)),
        )

    assert await painted(tmp_path, root(), [ScrollBy(HANDLE, y=2)]) == [
        ["at 0", "line 0", "line 1"],
        ["at 2", "line 2", "line 3"],
    ]


def unsettled_warnings(caplog: pytest.LogCaptureFixture) -> int:
    """How many times the app warned that it painted a frame whose measurements hadn't settled."""
    return sum(record.getMessage().startswith("Painted a frame with stale measurements") for record in caplog.records)


@component
def grows(widths: list[int]) -> Div:
    width = use_rects().border.width
    widths.append(width)
    return Div(style=size(width + 1, 1))


async def test_a_component_that_grows_whenever_it_measures_itself_paints_stale_and_warns_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    widths: list[int] = []

    with caplog.at_level(logging.WARNING, logger="counterweight._app"):
        await app(grows(widths), headless=True, dimensions=(20, 2), autopilot=[Quit()])

    # Each render reads the width the one before it set, across frames as well as within them.
    assert widths == list(range(len(widths)))
    # More renders than one frame's, so frames after the first carry on from where the last left off.
    assert len(widths) > 1 + SETTLING_PASSES
    assert unsettled_warnings(caplog) == 1


async def test_a_frame_that_fails_to_settle_after_one_that_settled_warns_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @component
    def grows_until_toggled() -> Div:
        is_growing, set_growing = use_state(True)
        width = use_rects().border.width

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_growing(not is_growing)

        return Div(style=size(width + 1 if is_growing else 3, 1), on_input=on_input)

    with caplog.at_level(logging.WARNING, logger="counterweight._app"):
        await app(
            grows_until_toggled(),
            headless=True,
            dimensions=(20, 2),
            autopilot=[KeyPressed(key="s"), KeyPressed(key="g"), Quit()],
        )

    assert unsettled_warnings(caplog) == 2


async def test_a_component_that_grows_whenever_it_measures_itself_raises_under_the_purity_check() -> None:
    with pytest.raises(UnsettledMeasurements, match=f"^grows still read stale measurements after {SETTLING_PASSES}"):
        await app(grows([]), headless=True, dimensions=(20, 2), autopilot=[Quit()], check_purity=True)


async def test_a_measurement_that_hides_a_component_that_just_gained_focus_moves_focus_without_raising(
    tmp_path: Path,
) -> None:
    @component
    def label(is_hidden: bool) -> Text:
        focus = use_focus(auto_focus=True)
        return Text(content="on" if focus.is_focused else "off", style=display_none if is_hidden else col)

    @component
    def hides_once_measured() -> Div:
        is_measured = use_rects(HANDLE).border.width > 0
        return Div(children=(label(is_measured),))

    @component
    def root() -> Div:
        is_mounted, set_mounted = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_mounted(True)

        return Div(
            style=col,
            on_input=on_input,
            children=(hides_once_measured(), Div(handle=HANDLE, style=size(2, 1))) if is_mounted else (),
        )

    assert (await painted(tmp_path, root(), [KeyPressed(key="m")]))[-1] == ["", "", ""]


@component
def sized_from_handle() -> Div:
    width = use_rects(HANDLE).border.width
    return Div(handle=SIZED, style=size(width, 1), children=(Text(content="=" * width),))


@component
def width_of_sized() -> Text:
    return Text(content=str(use_rects(SIZED).border.width))


async def test_a_chain_of_components_that_each_measure_the_one_before_settles_before_the_first_frame_paints(
    tmp_path: Path,
) -> None:
    @component
    def root() -> Div:
        return Div(
            style=col,
            children=(
                Div(handle=HANDLE, style=size(3, 1), children=(Text(content="###"),)),
                sized_from_handle(),
                width_of_sized(),
            ),
        )

    assert await painted(tmp_path, root(), []) == [["###", "===", "3"]]


async def test_an_auto_focus_component_that_hides_itself_once_focused_raises_beside_a_stale_measurement() -> None:
    @component
    def hides_once_focused() -> Text:
        focus = use_focus(auto_focus=True)
        return Text(content="shy", style=display_none if focus.is_focused else col)

    @component
    def root() -> Div:
        return Div(style=col, children=(hides_once_focused(), Div(handle=HANDLE, style=size(2, 1)), width_of_handle()))

    with pytest.raises(UnsettledFocus, match="hid itself"):
        await app(root(), headless=True, dimensions=(WIDTH, HEIGHT), autopilot=[Quit()])


async def test_a_waiting_focus_on_focuses_a_component_that_a_measurement_mounts_before_the_frame_paints(
    tmp_path: Path,
) -> None:
    @component
    def field() -> Text:
        focus = use_focus(handle=FIELD)
        return Text(content="on" if focus.is_focused else "off")

    @component
    def mounts_once_measured() -> Div:
        is_measured = use_rects(HANDLE).border.width > 0
        return Div(children=(field(),) if is_measured else ())

    @component
    def root() -> Div:
        is_mounted, set_mounted = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> FocusOn:
            set_mounted(True)
            return FocusOn(FIELD)

        return Div(
            style=col,
            on_input=on_input,
            children=(mounts_once_measured(), Div(handle=HANDLE, style=size(2, 1))) if is_mounted else (),
        )

    assert (await painted(tmp_path, root(), [KeyPressed(key="m")]))[-1] == ["on", "", ""]
