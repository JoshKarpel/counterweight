from __future__ import annotations

from asyncio import CancelledError, Event, create_task, wait_for
from contextlib import suppress
from datetime import UTC, datetime, timedelta, timezone

import pytest

from counterweight.app import app
from counterweight.clock import Instant, frozen_clock, system_clock, tick_index, until_next_tick
from counterweight.components import component
from counterweight.controls import AdvanceClock, Quit, Screenshot
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_clock, use_state
from counterweight.layout import NO_LAYOUTS
from counterweight.output import Frame
from counterweight.shadow import ShadowUpdate, until_due, update_shadow
from tests.rendering import state_set_keys, state_sets

# 26 seconds past the minute.
MOUNTED = Instant(wall=datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC), monotonic=timedelta(seconds=7))


@component
def clock_text(interval: timedelta) -> Text:
    tick = use_clock(interval)
    return Text(
        content=f"{tick.now:%H:%M:%S.%f} "
        f"start={tick.since_start.total_seconds():g} "
        f"mount={tick.since_mount.total_seconds():g}"
    )


SECONDS = Div(children=[clock_text(timedelta(seconds=1)).with_key("seconds")])
SECONDS_AND_MINUTES = Div(
    children=[
        clock_text(timedelta(seconds=1)).with_key("seconds"),
        clock_text(timedelta(minutes=1)).with_key("minutes"),
    ]
)


def render(root: AnyElement, previous: ShadowUpdate | None, instant: Instant) -> ShadowUpdate:
    return update_shadow(
        root, None if previous is None else previous.tree, NO_LAYOUTS, instant=instant, check_purity=True
    )


def texts(update: ShadowUpdate) -> list[object]:
    return [node.element.content for node in update.tree.nodes if isinstance(node.element, Text)]


def ran(update: ShadowUpdate) -> list[str | None]:
    """The keys of the components a render ran."""
    ran_hooks = {id(hooks) for hooks in update.ran}
    return [
        node.component.key for node in update.tree.nodes if node.component is not None and id(node.hooks) in ran_hooks
    ]


def test_the_reading_taken_on_mount_is_the_frames_instant() -> None:
    assert texts(render(SECONDS, None, MOUNTED)) == ["15:09:26.000000 start=7 mount=0"]


def test_a_reused_component_reruns_with_a_new_reading_once_its_tick_passes() -> None:
    update = render(SECONDS, render(SECONDS, None, MOUNTED), MOUNTED + timedelta(seconds=1.25))

    assert (ran(update), texts(update)) == (["seconds"], ["15:09:27.250000 start=8.25 mount=1.25"])


def test_a_reused_component_doesnt_rerun_within_its_tick() -> None:
    first = render(SECONDS, None, MOUNTED + timedelta(seconds=0.25))

    assert ran(render(SECONDS, first, MOUNTED + timedelta(seconds=0.75))) == []


def test_each_new_reading_measures_from_the_mount() -> None:
    first = render(SECONDS, None, MOUNTED)
    second = render(SECONDS, first, MOUNTED + timedelta(seconds=1))

    update = render(SECONDS, second, MOUNTED + timedelta(seconds=3.5))

    assert texts(update) == ["15:09:29.500000 start=10.5 mount=3.5"]


@component
def clock_with_counter() -> Div:
    count, set_count = use_state(0)
    tick = use_clock(timedelta(minutes=1))
    return Div(
        on_key=lambda _: set_count(count + 1),
        children=[Text(content=f"{count} {tick.now:%H:%M:%S}")],
    )


def test_rerunning_for_another_reason_within_a_tick_keeps_the_reading() -> None:
    root = clock_with_counter()
    with state_sets() as queue:
        first = update_shadow(root, None, NO_LAYOUTS, check_purity=True, instant=MOUNTED)
        on_key = first.tree.root.element.on_key
        assert on_key is not None
        on_key(KeyPressed(key="a"))

        update = update_shadow(
            root,
            first.tree,
            NO_LAYOUTS,
            state_set_keys(queue),
            check_purity=True,
            instant=MOUNTED + timedelta(seconds=1),
        )

    assert texts(update) == ["1 15:09:26"]


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        pytest.param(timedelta(seconds=33), ["seconds"], id="second"),
        pytest.param(timedelta(seconds=34), ["seconds", "minutes"], id="minute"),
    ],
)
def test_clocks_with_different_intervals_tick_together_on_the_wall_clock(
    elapsed: timedelta, expected: list[str]
) -> None:
    first = render(SECONDS_AND_MINUTES, None, MOUNTED)

    assert ran(render(SECONDS_AND_MINUTES, first, MOUNTED + elapsed)) == expected


def test_a_wall_clock_set_back_takes_a_new_reading() -> None:
    set_back = Instant(wall=MOUNTED.wall - timedelta(hours=1), monotonic=MOUNTED.monotonic + timedelta(seconds=2))

    update = render(SECONDS, render(SECONDS, None, MOUNTED), set_back)

    assert texts(update) == ["14:09:26.000000 start=9 mount=2"]


@pytest.mark.parametrize("interval", [timedelta(), timedelta(seconds=-1)], ids=["zero", "negative"])
def test_a_non_positive_interval_raises(interval: timedelta) -> None:
    with pytest.raises(ValueError, match="positive interval"):
        render(Div(children=[clock_text(interval)]), None, MOUNTED)


def test_nothing_is_due_in_a_tree_that_doesnt_read_the_clock() -> None:
    update = render(Div(children=[Text(content="static")]), None, MOUNTED)

    assert until_due(update.tree, MOUNTED) is None


def test_the_tree_is_due_when_its_soonest_clock_ticks() -> None:
    root = Div(
        children=[
            clock_text(timedelta(minutes=1)).with_key("minutes"),
            clock_text(timedelta(seconds=10)).with_key("ten-seconds"),
        ]
    )
    update = render(root, None, MOUNTED)

    assert until_due(update.tree, MOUNTED + timedelta(seconds=1)) == timedelta(seconds=3)


def test_a_tree_with_a_due_clock_is_due_now() -> None:
    update = render(Div(children=[clock_text(timedelta(seconds=10))]), None, MOUNTED)

    assert until_due(update.tree, MOUNTED + timedelta(seconds=4)) == timedelta()


def test_an_unmounted_clock_is_never_due() -> None:
    first = render(SECONDS, None, MOUNTED)

    update = render(Div(children=[Text(content="gone")]), first, MOUNTED)

    assert until_due(update.tree, MOUNTED + timedelta(seconds=1)) is None


INDIA = timezone(timedelta(hours=5, minutes=30))


@pytest.mark.parametrize(
    ("wall", "interval", "expected"),
    [
        pytest.param(
            datetime(2026, 3, 14, 15, 9, 26, 500_000, tzinfo=UTC), timedelta(seconds=1), timedelta(seconds=0.5), id="1s"
        ),
        pytest.param(
            datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC), timedelta(minutes=1), timedelta(seconds=34), id="1m"
        ),
        pytest.param(datetime(2026, 3, 14, 15, 9, tzinfo=INDIA), timedelta(hours=1), timedelta(minutes=51), id="1h"),
        pytest.param(datetime(2026, 3, 14, 23, 0, tzinfo=INDIA), timedelta(days=1), timedelta(hours=1), id="1d"),
        pytest.param(datetime(2026, 3, 14, 15, 10), timedelta(minutes=1), timedelta(minutes=1), id="on-a-tick"),
    ],
)
def test_ticks_start_on_the_local_wall_clock(wall: datetime, interval: timedelta, expected: timedelta) -> None:
    assert until_next_tick(wall, interval) == expected


def test_a_tick_ends_where_the_next_begins() -> None:
    wall = datetime(2026, 3, 14, 15, 9, 26, tzinfo=INDIA)
    interval = timedelta(seconds=7)
    boundary = wall + until_next_tick(wall, interval)

    assert (tick_index(boundary - timedelta(microseconds=1), interval), tick_index(boundary, interval)) == (
        tick_index(wall, interval),
        tick_index(wall, interval) + 1,
    )


async def test_advancing_a_frozen_clock_rerenders_the_components_reading_it() -> None:
    frames: list[str] = []

    def capture(frame: Frame) -> None:
        frames.append(frame.text(ansi=False).strip())

    await app(
        clock_text(timedelta(seconds=1)),
        headless=True,
        dimensions=(50, 1),
        autopilot=[
            Screenshot(handler=capture),
            AdvanceClock(by=timedelta(seconds=90)),
            Screenshot(handler=capture),
            Quit(),
        ],
        check_purity=True,
        clock=frozen_clock(MOUNTED.wall),
    )

    assert frames == [
        "15:09:26.000000 start=0 mount=0",
        "15:10:56.000000 start=90 mount=90",
    ]


async def test_the_app_renders_each_tick_without_any_input() -> None:
    nows: set[datetime] = set()
    ticked_three_times = Event()

    @component
    def recorder() -> Text:
        tick = use_clock(timedelta(milliseconds=10))
        nows.add(tick.now)
        if len(nows) >= 3:
            ticked_three_times.set()
        return Text(content="")

    task = create_task(app(recorder(), headless=True, dimensions=(20, 1), clock=system_clock))
    try:
        await wait_for(ticked_three_times.wait(), timeout=5)
    finally:
        task.cancel()
        with suppress(CancelledError):
            await task

    assert ticked_three_times.is_set()


async def test_advances_add_up_and_time_since_start_counts_from_the_first_reading() -> None:
    frames: list[str] = []

    def capture(frame: Frame) -> None:
        frames.append(frame.text(ansi=False).strip())

    await app(
        clock_text(timedelta(seconds=1)),
        headless=True,
        dimensions=(50, 1),
        autopilot=[
            Screenshot(handler=capture),
            AdvanceClock(by=timedelta(seconds=30)),
            AdvanceClock(by=timedelta(seconds=60)),
            Screenshot(handler=capture),
            Quit(),
        ],
        check_purity=True,
        clock=lambda: MOUNTED,
    )

    assert frames == [
        "15:09:26.000000 start=0 mount=0",
        "15:10:56.000000 start=90 mount=90",
    ]
