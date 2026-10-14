"""Helpers for tests that drive `update_shadow` directly, standing in for the parts of the render loop they need."""

from __future__ import annotations

from asyncio import Queue
from asyncio import Task
from asyncio import TaskGroup
from asyncio import sleep
from asyncio import wait_for
from collections.abc import AsyncIterator
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import asynccontextmanager
from contextlib import contextmanager
from dataclasses import dataclass

from counterweight._context_vars import current_event_queue
from counterweight._utils import cancel_tasks
from counterweight.app import handle_effects
from counterweight.components import Component
from counterweight.elements import AnyElement
from counterweight.events import AnyEvent
from counterweight.events import StateSet
from counterweight.hooks.impls import NodeKey
from counterweight.layout import NO_LAYOUTS
from counterweight.shadow import ShadowTree
from counterweight.shadow import update_shadow

# Generous, so a loaded machine doesn't fail a test; each test that waits finishes as soon as what it waits for happens.
TIMEOUT = 10


@contextmanager
def state_sets() -> Iterator[Queue[AnyEvent]]:
    """Gives setters a queue to enqueue `StateSet` into, as the app loop would."""
    queue: Queue[AnyEvent] = Queue()
    token = current_event_queue.set(queue)
    try:
        yield queue
    finally:
        current_event_queue.reset(token)


def state_set_keys(queue: Queue[AnyEvent]) -> frozenset[NodeKey]:
    """Drains `queue`, returning the keys of the nodes whose state was set, as the render loop collects `dirty`."""
    keys: set[NodeKey] = set()
    while not queue.empty():
        event = queue.get_nowait()
        assert isinstance(event, StateSet), f"only setters put events here, but got {event!r}"
        keys.add(event.key)
    return frozenset(keys)


async def render(
    root: Component | AnyElement,
    previous: ShadowTree | None,
    task_group: TaskGroup,
    dirty: frozenset[NodeKey] = frozenset(),
) -> ShadowTree:
    """Reconciles one render and its effects, then yields once so newly started effects run to their first `await`."""
    update = update_shadow(root, previous, NO_LAYOUTS, dirty)
    await handle_effects(ran=update.ran, unmounted=update.unmounted, task_group=task_group)
    await sleep(0)
    return update.tree


def effect_tasks(shadow: ShadowTree) -> list[Task[None]]:
    """The tasks of every effect in the tree, to cancel before the test's task group exits."""
    return [effect.task for node in shadow.nodes for effect in node.hooks.effects if effect.task is not None]


@dataclass(slots=True)
class Mounted:
    """Renders an element tree, and renders it again as its components set state, as the app loop would."""

    task_group: TaskGroup
    queue: Queue[AnyEvent]
    root: Component | AnyElement | None = None
    tree: ShadowTree | None = None

    async def render(self, root: Component | AnyElement) -> None:
        self.root = root
        self.tree = await render(root, self.tree, self.task_group)

    async def wait_until(self, is_done: Callable[[], bool]) -> None:
        while not is_done():
            assert self.root is not None
            first = await wait_for(self.queue.get(), TIMEOUT)
            assert isinstance(first, StateSet)
            dirty = state_set_keys(self.queue) | {first.key}
            self.tree = await render(self.root, self.tree, self.task_group, dirty)

    async def unmount(self) -> None:
        assert self.tree is not None
        await cancel_tasks(effect_tasks(self.tree))


@asynccontextmanager
async def mounted() -> AsyncIterator[Mounted]:
    with state_sets() as queue:
        async with TaskGroup() as task_group:
            m = Mounted(task_group=task_group, queue=queue)
            try:
                yield m
            finally:
                await m.unmount()
