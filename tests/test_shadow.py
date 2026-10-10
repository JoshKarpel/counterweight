from __future__ import annotations

from asyncio import Queue, Task, TaskGroup, sleep
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from weakref import WeakSet

from counterweight._context_vars import current_event_queue, current_use_mouse_listeners
from counterweight._utils import cancel, forever
from counterweight.app import handle_effects
from counterweight.components import Component, component
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import AnyEvent
from counterweight.hooks import Mouse, Setter, use_effect, use_mouse, use_state
from counterweight.shadow import ShadowNode, update_shadow


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


async def cancel_all(active_effects: set[Task[None]]) -> None:
    """Stops effects a test left running, so a regression fails its assertion instead of hanging the `TaskGroup`."""
    for task in active_effects:
        await cancel(task)


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


async def test_component_replaced_by_element_stops_its_effect() -> None:
    log: list[str] = []

    async with TaskGroup() as tg:
        shadow, active = await render(Div(children=[logs_effect("A", log)]), None, set(), tg)
        shadow, active = await render(Div(children=[Div()]), shadow, active, tg)
        log_after_replacement = log.copy()
        await cancel_all(active)

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
            await cancel_all(active)
    finally:
        current_use_mouse_listeners.reset(token)

    assert (listener_count_while_mounted, listener_count_after_replacement) == (1, 0)
