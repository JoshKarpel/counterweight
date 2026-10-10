from __future__ import annotations

from asyncio import Queue, Task, TaskGroup, sleep
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from sys import getrecursionlimit
from weakref import WeakSet

import pytest

from counterweight._context_vars import current_event_queue, current_use_mouse_listeners
from counterweight._utils import cancel_tasks, forever
from counterweight.app import handle_effects
from counterweight.components import Component, component
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import AnyEvent
from counterweight.hooks import Mouse, Setter, use_effect, use_mouse, use_state
from counterweight.hooks.impls import Hooks
from counterweight.shadow import DuplicateKey, ShadowNode, update_shadow


@contextmanager
def event_queue() -> Iterator[Queue[AnyEvent]]:
    """Gives setters a queue to enqueue `StateSet` into, as the app loop would."""
    queue: Queue[AnyEvent] = Queue()
    token = current_event_queue.set(queue)
    try:
        yield queue
    finally:
        current_event_queue.reset(token)


async def render(
    root: Component | AnyElement,
    previous: ShadowNode | None,
    active_effects: set[Task[None]],
    task_group: TaskGroup,
) -> tuple[ShadowNode, set[Task[None]]]:
    """Reconciles one render and its effects, then yields once so newly started effects run to their first `await`."""
    shadow, _ = update_shadow(root, previous)
    active_effects = await handle_effects(shadow, active_effects=active_effects, task_group=task_group)
    await sleep(0)
    return shadow, active_effects


@component
def logs_effect(name: str, log: list[str]) -> Text:
    async def setup() -> None:
        log.append(f"start {name}")
        try:
            await forever()
        finally:
            log.append(f"stop {name}")

    use_effect(setup=setup, deps=())

    return Text(content=name)


@component
def logs_effect_per_dep(name: str, dep: int, log: list[str]) -> Text:
    async def setup() -> None:
        log.append(f"start {name} {dep}")
        try:
            await forever()
        finally:
            log.append(f"stop {name} {dep}")

    use_effect(setup=setup, deps=(dep,))

    return Text(content=name)


async def test_rerun_effect_stops_before_it_starts_again() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(logs_effect_per_dep("A", 1, log), None, set(), tg)
        shadow, active = await render(logs_effect_per_dep("A", 2, log), shadow, active, tg)
        log_after_rerun = log.copy()
        await cancel_tasks(active)

    assert log_after_rerun == ["start A 1", "stop A 1", "start A 2"]


async def test_unmounted_effect_stops_before_sibling_rerun_starts() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(
            Div(children=[logs_effect_per_dep("A", 1, log), logs_effect("B", log)]), None, set(), tg
        )
        shadow, active = await render(Div(children=[logs_effect_per_dep("A", 2, log)]), shadow, active, tg)
        log_after_rerender = log.copy()
        await cancel_tasks(active)

    assert log_after_rerender.index("stop B") < log_after_rerender.index("start A 2")


async def test_component_replaced_by_element_stops_its_effect() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(Div(children=[logs_effect("A", log)]), None, set(), tg)
        shadow, active = await render(Div(children=[Div()]), shadow, active, tg)
        log_after_replacement = log.copy()
        await cancel_tasks(active)

    assert log_after_replacement == ["start A", "stop A"]


async def test_component_nested_under_replaced_component_starts_with_initial_state() -> None:
    setters: list[Setter[int]] = []
    seen: list[int] = []

    @component
    def counter() -> Text:
        count, set_count = use_state(3)
        setters.append(set_count)
        seen.append(count)
        return Text(content=str(count))

    @component
    def wrapper() -> Div:
        return Div(children=[counter()])

    with event_queue():
        async with TaskGroup() as tg:
            shadow, active = await render(Div(children=[wrapper()]), None, set(), tg)
            setters[-1](7)
            await render(Div(children=[Div(children=[counter()])]), shadow, active, tg)

    assert seen == [3, 3]


async def test_use_mouse_listener_removed_when_component_replaced_by_element() -> None:
    listeners: WeakSet[Callable[[Mouse], None]] = WeakSet()
    token = current_use_mouse_listeners.set(listeners)

    @component
    def tracks_mouse() -> Text:
        use_mouse()
        return Text(content="mouse")

    try:
        async with TaskGroup() as tg:
            shadow, active = await render(Div(children=[tracks_mouse()]), None, set(), tg)
            listener_count_while_mounted = len(listeners)
            shadow, active = await render(Div(children=[Div()]), shadow, active, tg)
            listener_count_after_replacement = len(listeners)
            await cancel_tasks(active)
    finally:
        current_use_mouse_listeners.reset(token)

    assert (listener_count_while_mounted, listener_count_after_replacement) == (1, 0)


def leaf(name: str, *children: ShadowNode) -> ShadowNode:
    return ShadowNode(component=None, element=Text(content=name), hooks=Hooks(), children=list(children))


def test_walk_yields_nodes_in_pre_order() -> None:
    tree = leaf("root", leaf("a", leaf("a1"), leaf("a2")), leaf("b", leaf("b1")))

    names = [node.element.content for node in tree.walk() if isinstance(node.element, Text)]

    assert names == ["root", "a", "a1", "a2", "b", "b1"]


def test_walk_handles_trees_deeper_than_the_recursion_limit() -> None:
    depth = getrecursionlimit() * 2
    tree = leaf("bottom")
    for _ in range(depth):
        tree = leaf("link", tree)

    assert sum(1 for _ in tree.walk()) == depth + 1


@component
def remembers(name: str, setters: dict[str, Setter[str]], seen: dict[str, str]) -> Text:
    value, set_value = use_state("initial")
    setters[name] = set_value
    seen[name] = value
    return Text(content=value)


async def test_reordered_keyed_children_keep_their_state() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with event_queue():
        async with TaskGroup() as tg:
            shadow, active = await render(
                Div(children=[remembers(name, setters, seen).with_key(name) for name in ("x", "y")]), None, set(), tg
            )
            setters["x"]("x was set")
            setters["y"]("y was set")
            await render(
                Div(children=[remembers(name, setters, seen).with_key(name) for name in ("y", "x")]), shadow, active, tg
            )

    assert seen == {"x": "x was set", "y": "y was set"}


async def test_reordered_keyed_children_keep_their_effects_running() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(
            Div(children=[logs_effect(name, log).with_key(name) for name in ("x", "y")]), None, set(), tg
        )
        shadow, active = await render(
            Div(children=[logs_effect(name, log).with_key(name) for name in ("y", "x")]), shadow, active, tg
        )
        log_after_reorder = log.copy()
        await cancel_tasks(active)

    assert log_after_reorder == ["start x", "start y"]


async def test_keyed_children_after_a_removed_keyed_child_keep_their_state() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}

    with event_queue():
        async with TaskGroup() as tg:
            shadow, active = await render(
                Div(children=[remembers(name, setters, seen).with_key(name) for name in ("a", "b", "c")]),
                None,
                set(),
                tg,
            )
            setters["c"]("c was set")
            await render(
                Div(children=[remembers(name, setters, seen).with_key(name) for name in ("a", "c")]), shadow, active, tg
            )

    assert seen["c"] == "c was set"


async def test_inserting_a_keyed_child_at_the_front_mounts_only_that_child() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(
            Div(children=[logs_effect(name, log).with_key(name) for name in ("x", "y")]), None, set(), tg
        )
        shadow, active = await render(
            Div(children=[logs_effect(name, log).with_key(name) for name in ("w", "x", "y")]), shadow, active, tg
        )
        log_after_insert = log.copy()
        await cancel_tasks(active)

    assert log_after_insert == ["start x", "start y", "start w"]


async def test_unkeyed_child_after_a_removed_keyed_sibling_remounts() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(
            Div(children=[logs_effect("a", log).with_key("a"), logs_effect("u", log)]), None, set(), tg
        )
        shadow, active = await render(Div(children=[logs_effect("u", log)]), shadow, active, tg)
        log_after_removal = log.copy()
        await cancel_tasks(active)

    assert log_after_removal.count("start u") == 2


def test_duplicate_sibling_keys_raise() -> None:
    log: list[str] = []

    with pytest.raises(DuplicateKey):
        update_shadow(Div(children=[logs_effect("x", log).with_key(1), logs_effect("y", log).with_key(1)]), None)


async def test_setter_is_the_same_object_across_renders() -> None:
    setters: dict[str, Setter[str]] = {}
    seen: dict[str, str] = {}
    setters_by_render: list[Setter[str]] = []

    with event_queue():
        async with TaskGroup() as tg:
            shadow, active = await render(remembers("a", setters, seen), None, set(), tg)
            setters_by_render.append(setters["a"])
            setters["a"]("a was set")
            await render(remembers("a", setters, seen), shadow, active, tg)
            setters_by_render.append(setters["a"])

    assert setters_by_render[0] is setters_by_render[1]


async def test_effect_with_setter_in_deps_runs_once_across_renders() -> None:
    log: list[str] = []

    @component
    def depends_on_setter(label: str) -> Text:
        _, set_value = use_state(0)

        async def setup() -> None:
            log.append("start")
            await forever()

        use_effect(setup=setup, deps=(set_value,))

        return Text(content=label)

    async with TaskGroup() as tg:
        shadow, active = await render(depends_on_setter("first"), None, set(), tg)
        shadow, active = await render(depends_on_setter("second"), shadow, active, tg)
        shadow, active = await render(depends_on_setter("third"), shadow, active, tg)
        log_after_renders = log.copy()
        await cancel_tasks(active)

    assert log_after_renders == ["start"]
