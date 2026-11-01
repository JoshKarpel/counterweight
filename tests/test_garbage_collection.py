import gc
import weakref
from collections.abc import Callable
from collections.abc import Iterator

import pytest

from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_effect
from counterweight.hooks import use_state


@pytest.fixture(autouse=True)
def collector_enabled_afterwards() -> Iterator[None]:
    """Enables the collector after each test, so one that fails with it disabled doesn't disable it for the rest."""
    yield
    gc.enable()


class Node:
    """An object that can hold a reference to itself and be weakly referenced, to make cyclic garbage."""

    other: Node | None = None


def allocations_to_trigger_collections(collections: int) -> list[list[None]]:
    """Enough new containers to trigger `collections` collections of the youngest generation."""
    return [[] for _ in range(gc.get_threshold()[0] * collections)]


def rerenders_on_input() -> Callable[[InputEvent, Receiver], None]:
    """
    A handler that re-renders the calling component, so a component that's otherwise rendered only once,
    by the app's first render, which runs before its render loop starts and so outside any frame, runs in a frame.
    """
    count, set_count = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> None:
        set_count(count + 1)

    return on_input


# The key press that makes a component calling `rerenders_on_input` run in a frame.
RERENDER = KeyPressed(key="r")


@pytest.mark.parametrize(("collect_garbage_between_frames", "expected"), [(True, False), (False, True)])
async def test_the_collector_is_disabled_while_a_component_runs_only_with_the_option_on(
    collect_garbage_between_frames: bool, expected: bool
) -> None:
    seen: list[bool] = []

    @component
    def root() -> Div:
        seen.append(gc.isenabled())
        return Div(on_input=rerenders_on_input())

    await app(
        root(),
        headless=True,
        autopilot=[RERENDER, Quit()],
        collect_garbage_between_frames=collect_garbage_between_frames,
    )

    first, *frames = seen
    assert (first, frames) == (True, [expected])


async def test_the_collector_is_paused_while_a_component_runs_by_default() -> None:
    seen: list[bool] = []

    @component
    def root() -> Div:
        seen.append(gc.isenabled())
        return Div(on_input=rerenders_on_input())

    await app(root(), headless=True, autopilot=[RERENDER, Quit()])

    assert seen[1:] == [False]


async def test_no_collection_starts_during_a_frame_that_allocates_enough_for_several() -> None:
    runs = 0
    is_rendering = False
    # Whether a frame was rendering, for each collection that started.
    started_while_rendering: list[bool] = []

    def record(phase: str, info: dict[str, int]) -> None:
        if phase == "start":
            started_while_rendering.append(is_rendering)

    @component
    def root() -> Div:
        nonlocal runs, is_rendering
        runs += 1
        is_rendering = runs > 1
        allocations_to_trigger_collections(5)
        is_rendering = False
        return Div(on_input=rerenders_on_input())

    gc.callbacks.append(record)
    try:
        await app(root(), headless=True, autopilot=[RERENDER, Quit()], collect_garbage_between_frames=True)
    finally:
        gc.callbacks.remove(record)

    # The first render's allocations start collections, since it's not in a frame, so the callback was reached.
    assert runs == 2
    assert started_while_rendering
    assert not any(started_while_rendering)


async def test_a_cycle_from_a_frame_that_keeps_what_it_allocates_is_collected_before_the_next_frame() -> None:
    cycles: list[weakref.ref[Node]] = []
    # Kept past the frame, as a frame keeps the nodes of the tree it renders,
    # since the collector counts the objects allocated and not yet freed.
    kept: list[list[list[None]]] = []
    alive_on_next_frame: list[bool] = []

    @component
    def root() -> Div:
        frame, set_frame = use_state(0)

        if frame == 0:
            cycle = Node()
            cycle.other = cycle
            cycles.append(weakref.ref(cycle))
            del cycle
            kept.append(allocations_to_trigger_collections(2))
        else:
            # The cycle from the first render.
            alive_on_next_frame.append(any(cycle() is not None for cycle in cycles))

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_frame(1)

        return Div(on_input=on_input)

    await app(
        root(),
        headless=True,
        autopilot=[KeyPressed(key="n"), Quit()],
        collect_garbage_between_frames=True,
    )

    assert alive_on_next_frame == [False]


async def test_effects_and_handlers_run_with_the_collector_enabled() -> None:
    seen: list[tuple[str, bool]] = []

    @component
    def root() -> Div:
        async def effect() -> None:
            seen.append(("effect", gc.isenabled()))

        use_effect(effect, deps=())

        def on_input(event: InputEvent, _: Receiver) -> None:
            seen.append(("handler", gc.isenabled()))

        return Div(on_input=on_input)

    await app(
        root(),
        headless=True,
        autopilot=[KeyPressed(key="n"), Quit()],
        collect_garbage_between_frames=True,
    )

    assert sorted(seen) == [("effect", True), ("handler", True)]


async def test_the_collector_is_enabled_after_the_app_quits() -> None:
    @component
    def root() -> Div:
        return Div()

    await app(root(), headless=True, autopilot=[Quit()], collect_garbage_between_frames=True)

    assert gc.isenabled()


class Boom(Exception):
    pass


async def test_the_collector_is_enabled_after_a_component_raises_mid_frame() -> None:
    runs = 0

    @component
    def root() -> Div:
        nonlocal runs
        runs += 1
        on_input = rerenders_on_input()
        if runs == 2:
            raise Boom
        return Div(on_input=on_input)

    with pytest.raises(Boom):
        await app(root(), headless=True, autopilot=[RERENDER, Quit()], collect_garbage_between_frames=True)

    assert gc.isenabled()


async def test_a_collector_disabled_before_the_app_starts_stays_disabled() -> None:
    seen: list[bool] = []

    @component
    def root() -> Div:
        async def effect() -> None:
            seen.append(gc.isenabled())

        use_effect(effect, deps=())
        return Div()

    gc.disable()
    await app(root(), headless=True, autopilot=[Quit()], collect_garbage_between_frames=True)

    assert (seen, gc.isenabled()) == ([False], False)


async def test_a_collector_disabled_by_an_effect_after_a_paused_frame_stays_disabled() -> None:
    seen: list[bool] = []

    @component
    def root() -> Div:
        frame, set_frame = use_state(0)
        seen.append(gc.isenabled())

        async def disable_collector() -> None:
            gc.disable()

        use_effect(disable_collector, deps=())

        def on_input(event: InputEvent, _: Receiver) -> None:
            set_frame(frame + 1)

        return Div(on_input=on_input)

    await app(
        root(),
        headless=True,
        autopilot=[KeyPressed(key="n"), Quit()],
        collect_garbage_between_frames=True,
    )

    # The first render, before any frame, and the frame after the effect disabled it.
    assert (seen, gc.isenabled()) == ([True, False], False)
