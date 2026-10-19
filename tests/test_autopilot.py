from __future__ import annotations

from asyncio import Event
from asyncio import wait_for
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from counterweight.animation import FRAME_INTERVAL
from counterweight.app import app
from counterweight.autopilot import Autopilot
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import AutopilotTimedOut
from counterweight.autopilot import Wait
from counterweight.autopilot import WaitFor
from counterweight.autopilot import advance
from counterweight.autopilot import showing
from counterweight.autopilot import typed
from counterweight.clock import FrozenClock
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_clock
from counterweight.hooks import use_effect
from counterweight.hooks import use_progress
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.styles.styles import CELL_STYLE_DEFAULTS

BLANK = Frame(paint=Paint.blank(1, 1))

TIMEOUT = 5


async def drive(root: Component, dimensions: tuple[int, int], autopilot: list[AutopilotStep]) -> None:
    """Runs `root` headless under `autopilot`, failing rather than hanging if it never quits."""
    await wait_for(app(root, headless=True, dimensions=dimensions, autopilot=autopilot), timeout=TIMEOUT)


def blank() -> Frame:
    return BLANK


def never(frame: Frame) -> bool:
    return False


def always(frame: Frame) -> bool:
    return True


def test_an_autopilot_gives_its_events_and_controls_in_order_then_nothing() -> None:
    pilot = Autopilot(steps=iter([KeyPressed(key="a"), Quit()]))

    assert [pilot.next(0, blank) for _ in range(3)] == [KeyPressed(key="a"), Quit(), None]


def test_a_wait_holds_the_autopilot_back_until_its_duration_passes() -> None:
    pilot = Autopilot(steps=iter([Wait(timedelta(seconds=2)), Quit()]))

    assert [pilot.next(now, blank) for now in (10, 11.9, 12)] == [None, None, Quit()]


def test_a_wait_of_no_time_holds_nothing_back() -> None:
    assert Autopilot(steps=iter([Wait(timedelta()), Quit()])).next(10, blank) == Quit()


def test_waits_in_a_row_each_wait_their_duration_from_when_the_last_ended() -> None:
    pilot = Autopilot(steps=iter([Wait(timedelta(seconds=1)), Wait(timedelta(seconds=1)), Quit()]))

    assert [pilot.next(now, blank) for now in (0, 1, 1.5, 2)] == [None, None, None, Quit()]


def test_a_wait_for_a_condition_that_holds_holds_nothing_back() -> None:
    assert Autopilot(steps=iter([WaitFor(always, timeout=timedelta()), Quit()])).next(0, blank) == Quit()


def test_a_wait_for_holds_the_autopilot_back_until_its_condition_holds() -> None:
    shown = [False]
    pilot = Autopilot(steps=iter([WaitFor(lambda frame: shown[0], timeout=timedelta(seconds=5)), Quit()]))

    assert pilot.next(0, blank) is None
    shown[0] = True
    assert pilot.next(1, blank) == Quit()


def test_a_wait_for_gives_its_condition_the_frame_on_screen() -> None:
    seen: list[Frame] = []

    def records(frame: Frame) -> bool:
        seen.append(frame)
        return True

    Autopilot(steps=iter([WaitFor(records, timeout=timedelta())])).next(0, blank)

    assert seen == [BLANK]


def test_a_wait_for_whose_condition_never_holds_times_out() -> None:
    pilot = Autopilot(steps=iter([WaitFor(never, timeout=timedelta(seconds=5)), Quit()]))

    assert pilot.next(0, blank) is None
    assert pilot.next(4.9, blank) is None
    with pytest.raises(AutopilotTimedOut, match="never"):
        pilot.next(5, blank)


def test_an_autopilot_that_has_not_waited_has_waited_no_time() -> None:
    assert Autopilot(steps=iter([Quit()])).time_waited(10) == timedelta()


def test_a_wait_counts_the_time_it_has_waited_so_far() -> None:
    pilot = Autopilot(steps=iter([Wait(timedelta(seconds=2)), Quit()]))
    pilot.next(10, blank)

    assert pilot.time_waited(11.5) == timedelta(seconds=1.5)


def test_a_wait_counts_no_more_than_its_duration_however_late_it_ends() -> None:
    pilot = Autopilot(steps=iter([Wait(timedelta(seconds=2)), Quit()]))
    pilot.next(10, blank)
    pilot.next(12.75, blank)

    assert pilot.time_waited(20) == timedelta(seconds=2)


def test_a_wait_for_counts_the_time_until_its_condition_holds() -> None:
    shown = [False]
    pilot = Autopilot(steps=iter([WaitFor(lambda frame: shown[0], timeout=timedelta(seconds=5)), Quit()]))
    pilot.next(10, blank)
    shown[0] = True
    pilot.next(13.25, blank)

    assert pilot.time_waited(20) == timedelta(seconds=3.25)


def test_the_time_waited_adds_up_across_waits() -> None:
    pilot = Autopilot(
        steps=iter([Wait(timedelta(seconds=2)), KeyPressed(key="a"), WaitFor(never, timeout=timedelta(seconds=9))])
    )
    pilot.next(10, blank)
    pilot.next(12.5, blank)
    pilot.next(13, blank)

    assert pilot.time_waited(14) == timedelta(seconds=3)


def test_an_autopilot_that_is_not_waiting_has_no_deadline() -> None:
    assert Autopilot(steps=iter([Quit()])).until_deadline(0) is None


@pytest.mark.parametrize("step", [Wait(timedelta(seconds=3)), WaitFor(never, timeout=timedelta(seconds=3))])
def test_an_autopilot_that_is_waiting_wakes_when_its_wait_ends(step: Wait | WaitFor) -> None:
    pilot = Autopilot(steps=iter([step]))
    pilot.next(10, blank)

    assert [pilot.until_deadline(now) for now in (11, 14)] == [2, 0]


@component
def finishes_later(finished: Event) -> Text:
    """Shows "done" once `finished` is set, as a component waiting on a subprocess would."""
    is_done, set_is_done = use_state(False)

    async def wait() -> None:
        await finished.wait()
        set_is_done(True)

    use_effect(wait, deps=())
    return Text(content="done" if is_done else "busy")


async def screen_after(steps: list[AutopilotStep], finished: Event) -> str:
    frames: list[Frame] = []
    await drive(
        finishes_later(finished),
        (4, 1),
        [*steps, Screenshot(frames.append), Quit()],
    )
    return frames[0].text(ansi=False)


async def test_an_app_keeps_handling_events_while_its_autopilot_waits() -> None:
    finished = Event()
    finished.set()

    assert await screen_after([Wait(timedelta(milliseconds=20))], finished) == "done"


async def test_without_a_wait_the_autopilot_runs_ahead_of_work_the_app_is_doing() -> None:
    finished = Event()
    finished.set()

    assert await screen_after([], finished) == "busy"


async def test_an_autopilot_waiting_for_a_condition_resumes_once_a_frame_shows_it() -> None:
    finished = Event()
    frames: list[Frame] = []
    await drive(
        finishes_later(finished),
        (4, 1),
        [
            Wait(timedelta(milliseconds=5)),
            Screenshot(frames.append),
            Screenshot(lambda frame: finished.set()),
            WaitFor(lambda frame: frame.text(ansi=False) == "done", timeout=timedelta(seconds=5)),
            Screenshot(frames.append),
            Quit(),
        ],
    )

    assert [frame.text(ansi=False) for frame in frames] == ["busy", "done"]


async def test_an_app_raises_when_its_autopilot_waits_too_long_for_a_condition() -> None:
    with pytest.raises(AutopilotTimedOut):
        await drive(
            finishes_later(Event()),
            (4, 1),
            [WaitFor(never, timeout=timedelta(milliseconds=10)), Quit()],
        )


@component
def two_letters() -> Text:
    second, set_second = use_state("b")

    def on_input(event: InputEvent, _: Receiver) -> None:
        set_second("c")

    return Text(content="a" + second, on_input=on_input)


async def test_a_wait_for_sees_the_whole_screen_not_only_what_the_last_frame_changed() -> None:
    frames: list[Frame] = []

    await drive(
        two_letters(),
        (2, 1),
        [
            KeyPressed(key="x"),
            WaitFor(lambda frame: frame.text(ansi=False) == "ac", timeout=timedelta(seconds=5)),
            Screenshot(frames.append),
            Quit(),
        ],
    )

    assert frames[0].text(ansi=False) == "ac"


@component
def time_since_mount() -> Text:
    tick = use_clock(timedelta(milliseconds=10))
    return Text(content=f"{tick.since_mount // timedelta(milliseconds=10)}")


async def test_a_frozen_clock_runs_while_the_autopilot_waits_for_a_condition() -> None:
    frames: list[Frame] = []

    await wait_for(
        app(
            time_since_mount(),
            headless=True,
            dimensions=(4, 1),
            clock=FrozenClock(datetime(2026, 3, 14, tzinfo=UTC)),
            autopilot=[
                WaitFor(lambda frame: frame.text(ansi=False).strip() == "3", timeout=timedelta(seconds=5)),
                Screenshot(frames.append),
                Quit(),
            ],
        ),
        timeout=TIMEOUT,
    )

    assert frames[0].text(ansi=False).strip() == "3"


async def test_a_wait_moves_a_frozen_clock_on_by_exactly_its_duration() -> None:
    frames: list[Frame] = []

    await wait_for(
        app(
            time_since_mount(),
            headless=True,
            dimensions=(4, 1),
            clock=FrozenClock(datetime(2026, 3, 14, tzinfo=UTC)),
            autopilot=[Wait(timedelta(milliseconds=55)), Screenshot(frames.append), Quit()],
        ),
        timeout=TIMEOUT,
    )

    assert frames[0].text(ansi=False).strip() == "5"


def test_typed_presses_a_key_for_each_grapheme_cluster() -> None:
    assert typed("ab日👩‍💻") == [KeyPressed(key=key) for key in ("a", "b", "日", "👩‍💻")]


def test_typed_presses_enter_for_a_newline_and_tab_for_a_tab() -> None:
    assert typed("a\n\t") == [KeyPressed(key="a"), KeyPressed(key=Key.Enter), KeyPressed(key=Key.Tab)]


def test_typed_takes_its_pause_after_each_key() -> None:
    pause = Wait(timedelta(milliseconds=90))

    assert typed("ab", pause=pause) == [KeyPressed(key="a"), pause, KeyPressed(key="b"), pause]


def frame_showing(text: str) -> Frame:
    paint = Paint.blank(8, 1)
    for x, character in enumerate(text):
        paint[x, 0] = Cell(character, CELL_STYLE_DEFAULTS)
    return Frame(paint=paint)


@pytest.mark.parametrize(("shown", "expected"), [("a prompt", True), ("nothing", False)])
def test_showing_waits_for_its_text_to_be_on_screen(shown: str, expected: bool) -> None:
    assert showing("prompt").condition(frame_showing(shown)) is expected


def test_showing_gives_up_after_its_timeout() -> None:
    assert showing("prompt", timeout=timedelta(seconds=3)).timeout == timedelta(seconds=3)


@pytest.mark.parametrize(
    ("by", "expected"),
    [
        pytest.param(timedelta(milliseconds=150), [timedelta(milliseconds=50)] * 3, id="whole-steps"),
        pytest.param(
            timedelta(milliseconds=120),
            [timedelta(milliseconds=50), timedelta(milliseconds=50), timedelta(milliseconds=20)],
            id="with-a-shorter-last-step",
        ),
        pytest.param(timedelta(), [], id="nothing"),
    ],
)
def test_advance_moves_the_clock_a_step_at_a_time(by: timedelta, expected: list[timedelta]) -> None:
    assert advance(by, step=timedelta(milliseconds=50)) == [AdvanceClock(by=step) for step in expected]


def test_advance_steps_a_frame_of_the_animation_hooks_at_a_time_by_default() -> None:
    assert advance(FRAME_INTERVAL * 2) == [AdvanceClock(by=FRAME_INTERVAL)] * 2


@pytest.mark.parametrize(
    ("by", "step"),
    [
        pytest.param(timedelta(seconds=-1), timedelta(seconds=1), id="backwards"),
        pytest.param(timedelta(seconds=1), timedelta(), id="no-step"),
    ],
)
def test_advance_without_a_way_forward_raises(by: timedelta, step: timedelta) -> None:
    with pytest.raises(ValueError, match="isn't negative and a positive step"):
        advance(by, step)


async def test_advancing_plays_an_animation_a_frame_at_a_time() -> None:
    texts: list[str] = []

    @component
    def animated() -> Text:
        return Text(content=f"{use_progress(timedelta(milliseconds=100)):g}")

    await app(
        animated(),
        headless=True,
        dimensions=(4, 1),
        clock=FrozenClock(datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)),
        autopilot=[
            *(advanced, Screenshot(handler=lambda frame: texts.append(frame.text(ansi=False).strip())))
            for advanced in advance(timedelta(milliseconds=100))
        ]
        + [Quit()],
    )

    assert texts == ["0.5", "1"]
