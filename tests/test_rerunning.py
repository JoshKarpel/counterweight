from __future__ import annotations

from asyncio import Event, Queue, Task, TaskGroup, create_task, sleep, wait_for
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight._context_vars import current_event_queue
from counterweight._utils import cancel_tasks, forever
from counterweight.app import app, handle_effects
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, ToggleBorderHealing
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import AnyEvent, StateSet, TerminalResized
from counterweight.geometry import Region
from counterweight.hooks import Rects, Setter, use_effect, use_rects, use_state
from counterweight.hooks.hooks import rects_in
from counterweight.hooks.impls import Hooks, NodeKey
from counterweight.layout import NO_LAYOUTS, Layouts, ResolvedLayout
from counterweight.shadow import ShadowNode, dirty_paths, is_dirty, update_shadow

type Shape = tuple[tuple[str, Shape], ...]


@dataclass(frozen=True, slots=True)
class Calls:
    """Which components ran, in order, and each one's setter, by name."""

    names: list[str] = field(default_factory=list)
    setters: dict[str, Setter[int]] = field(default_factory=dict)


@component
def counted(name: str, children: Shape, calls: Calls) -> Div:
    _, set_count = use_state(0)
    calls.names.append(name)
    calls.setters[name] = set_count
    return Div(children=[counted(child, grandchildren, calls) for child, grandchildren in children])


@contextmanager
def state_sets() -> Iterator[Queue[AnyEvent]]:
    queue: Queue[AnyEvent] = Queue()
    token = current_event_queue.set(queue)
    try:
        yield queue
    finally:
        current_event_queue.reset(token)


def set_state(calls: Calls, queue: Queue[AnyEvent], *names: str) -> frozenset[NodeKey]:
    """Steps each named component's state, and returns the keys the render loop would collect from the queue."""
    for name in names:
        calls.setters[name](lambda count: count + 1)

    return state_set_keys(queue)


def state_set_keys(queue: Queue[AnyEvent]) -> frozenset[NodeKey]:
    keys: set[NodeKey] = set()
    while not queue.empty():
        match queue.get_nowait():
            case StateSet(key=key):
                keys.add(key)
            case _:
                pass
    return frozenset(keys)


def rerun(root: Component | AnyElement, calls: Calls, *names: str) -> tuple[ShadowNode, ShadowNode]:
    """Renders `root`, sets the named components' state, and renders the same `root` again."""
    with state_sets() as queue:
        previous = update_shadow(root, None, NO_LAYOUTS).tree
        dirty = set_state(calls, queue, *names)
        calls.names.clear()
        return previous, update_shadow(root, previous, NO_LAYOUTS, dirty).tree


def test_sibling_state_change_does_not_rerun_a_component() -> None:
    calls = Calls()

    rerun(counted("root", (("a", ()), ("b", ())), calls), calls, "b")

    assert calls.names == ["b"]


def test_parent_state_change_reruns_its_children() -> None:
    calls = Calls()

    rerun(counted("root", (("a", ()), ("b", ())), calls), calls, "root")

    assert calls.names == ["root", "a", "b"]


def test_grandchild_state_change_reruns_only_the_grandchild() -> None:
    calls = Calls()

    rerun(counted("root", (("middle", (("leaf", ()),)),), calls), calls, "leaf")

    assert calls.names == ["leaf"]


def test_ancestors_of_a_rerun_component_keep_their_elements() -> None:
    calls = Calls()

    previous, next = rerun(counted("root", (("middle", (("leaf", ()),)),), calls), calls, "leaf")

    assert (next.element is previous.element, next.children[0].element is previous.children[0].element) == (True, True)


def test_unchanged_frame_reuses_the_whole_tree() -> None:
    calls = Calls()

    previous, next = rerun(counted("root", (("a", ()),), calls), calls)

    assert next is previous


@component
def holds(child: Component, calls: Calls) -> Div:
    _, set_count = use_state(0)
    calls.names.append("holder")
    calls.setters["holder"] = set_count
    return Div(children=[child])


def test_component_object_reused_by_its_rerun_parent_is_not_rerun() -> None:
    calls = Calls()

    rerun(holds(counted("held", (), calls), calls), calls, "holder")

    assert calls.names == ["holder"]


@component
def starts_every_render(log: list[str]) -> Text:
    async def setup() -> None:
        log.append("start")
        await forever()

    use_effect(setup)

    return Text(content="effect")


async def render_with_effects(
    root: Component | AnyElement,
    previous: ShadowNode | None,
    task_group: TaskGroup,
    dirty: frozenset[NodeKey] = frozenset(),
) -> ShadowNode:
    update = update_shadow(root, previous, NO_LAYOUTS, dirty)
    await handle_effects(ran=update.ran, unmounted=update.unmounted, task_group=task_group)
    await sleep(0)
    return update.tree


def effect_tasks(shadow: ShadowNode) -> list[Task[None]]:
    return [effect.task for node in shadow.walk() for effect in node.hooks.effects if effect.task is not None]


async def test_effect_without_deps_of_a_reused_component_does_not_rerun() -> None:
    log: list[str] = []
    calls = Calls()
    root = Div(children=[starts_every_render(log), counted("sibling", (), calls)])

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render_with_effects(root, None, tg)
            shadow = await render_with_effects(root, shadow, tg, set_state(calls, queue, "sibling"))
            log_after_sibling_rerun = log.copy()
            await cancel_tasks(effect_tasks(shadow))

    assert log_after_sibling_rerun == ["start"]


@component
def shows(log: list[str], setters: dict[str, Setter[bool]]) -> Div:
    is_shown, set_is_shown = use_state(True)
    setters["shows"] = set_is_shown

    @component
    def child() -> Text:
        async def setup() -> None:
            try:
                await forever()
            finally:
                log.append("stop")

        use_effect(setup, deps=())
        return Text(content="child")

    return Div(children=[child()] if is_shown else [])


async def test_effect_stops_when_its_component_is_unmounted_by_a_rerun_parent() -> None:
    log: list[str] = []
    setters: dict[str, Setter[bool]] = {}
    root = shows(log, setters)

    with state_sets() as queue:
        async with TaskGroup() as tg:
            shadow = await render_with_effects(root, None, tg)
            setters["shows"](False)
            await render_with_effects(root, shadow, tg, state_set_keys(queue))

    assert log == ["stop"]


MOVED = ResolvedLayout(
    content=Region(left=1, top=2, right=3, bottom=4),
    padding=Region(left=1, top=2, right=3, bottom=4),
    border=Region(left=1, top=2, right=3, bottom=4),
    margin=Region(left=1, top=2, right=3, bottom=4),
    order=0,
)


@component
def measures(calls: Calls) -> Div:
    use_rects()
    calls.names.append("measures")
    return Div()


@pytest.mark.parametrize(
    ("layout", "expected"),
    [
        pytest.param(MOVED, ["measures"], id="moved"),
        pytest.param(None, [], id="unmoved"),
    ],
)
def test_component_calling_use_rects_reruns_only_when_its_layout_moved(
    layout: ResolvedLayout | None, expected: list[str]
) -> None:
    calls = Calls()
    root = measures(calls)
    previous = update_shadow(root, None, NO_LAYOUTS).tree
    layouts = Layouts(in_paint_order=(), by_key={} if layout is None else {previous.key: layout})
    calls.names.clear()

    update_shadow(root, previous, layouts)

    assert calls.names == expected


@pytest.mark.parametrize(
    ("autopilot", "expected_renders"),
    [
        pytest.param((TerminalResized(dimensions=(30, 12)),), 3, id="resize"),
        pytest.param((ToggleBorderHealing(),), 2, id="no-state-change"),
    ],
)
async def test_whole_tree_rerenders_only_on_resize(
    autopilot: tuple[AnyEvent | AnyControl, ...], expected_renders: int
) -> None:
    renders: list[str] = []

    @component
    def leaf() -> Text:
        renders.append("leaf")
        return Text(content="leaf")

    @component
    def root() -> Div:
        return Div(children=[leaf()])

    await app(root, headless=True, dimensions=(20, 10), autopilot=(*autopilot, Quit()))

    # The warmup render and the first painted frame each render every component.
    assert len(renders) == expected_renders


async def test_effects_start_on_the_first_painted_frame() -> None:
    started = Event()

    @component
    def root() -> Div:
        async def setup() -> None:
            started.set()
            await forever()

        use_effect(setup, deps=())
        return Div()

    # Nothing yields to the event loop while an autopilot runs, so the app runs with none until the effect starts.
    running = create_task(app(root, headless=True, dimensions=(20, 10)))
    try:
        await wait_for(started.wait(), timeout=5)
    finally:
        running.cancel()
        await running

    assert started.is_set()


@st.composite
def dirty_trees(draw: st.DrawFn) -> tuple[ShadowNode, frozenset[NodeKey]]:
    """A tree of nodes, some with state set and some whose `use_rects` result has moved, and the set keys."""
    shape = draw(st.recursive(st.just(()), lambda children: st.lists(children, max_size=3).map(tuple), max_leaves=12))

    def build(shape: tuple[object, ...]) -> ShadowNode:
        hooks = Hooks()
        hooks.rects = draw(st.sampled_from([None, rects_in(NO_LAYOUTS, hooks.key), MOVED_RECTS]))
        return ShadowNode(
            component=None,
            element=Text(content=""),
            hooks=hooks,
            children=tuple(build(child) for child in shape if isinstance(child, tuple)),
        )

    tree = build(shape)
    keys = [node.key for node in tree.walk()]
    dirty = draw(st.frozensets(st.sampled_from(keys)))
    return tree, dirty


MOVED_RECTS = Rects(content=MOVED.content, padding=MOVED.padding, border=MOVED.border, margin=MOVED.margin)


@given(tree_and_dirty=dirty_trees())
def test_dirty_paths_are_the_nodes_with_a_dirty_node_in_their_subtree(
    tree_and_dirty: tuple[ShadowNode, frozenset[NodeKey]],
) -> None:
    tree, dirty = tree_and_dirty

    brute_force = frozenset(
        node.key for node in tree.walk() if any(is_dirty(below, dirty, NO_LAYOUTS) for below in node.walk())
    )

    assert dirty_paths(tree, dirty, NO_LAYOUTS) == brute_force
