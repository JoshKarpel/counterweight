from __future__ import annotations

from asyncio import Queue
from asyncio import TaskGroup
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    from counterweight.clock import Instant
    from counterweight.components import Component
    from counterweight.events import AnyEvent
    from counterweight.hooks import Mouse
    from counterweight.hooks.impls import Hooks
    from counterweight.hooks.impls import NodeKey
    from counterweight.layout import Layouts

# What belongs to one app, set only while its render loop reconciles (see `app_scope`),
# so a hook that needs one after the render, such as a setter or an effect, captures it while rendering.
current_event_queue: ContextVar[Queue[AnyEvent]] = ContextVar("current_event_queue")
# The task group the app runs effects in, so an effect can leave its teardown to finish in the background.
current_task_group: ContextVar[TaskGroup] = ContextVar("current_task_group")
current_use_mouse_listeners: ContextVar[WeakSet[Callable[[Mouse], None]]] = ContextVar("current_use_mouse_listeners")

current_hook_idx: ContextVar[int] = ContextVar("current_hook_idx")
current_hook_state: ContextVar[Hooks] = ContextVar("current_hook_state")
current_layouts: ContextVar[Layouts] = ContextVar("current_layouts")
# The focused node's key while a component is called, so `use_focus` can tell its component whether it's focused.
current_focused: ContextVar[NodeKey | None] = ContextVar("current_focused")
current_instant: ContextVar[Instant] = ContextVar("current_instant")
# The component being called when `check_purity` is on, so `use_memo` can check its cached values and name it.
current_purity_checked: ContextVar[Component | None] = ContextVar("current_purity_checked", default=None)


@contextmanager
def app_scope(
    event_queue: Queue[AnyEvent],
    task_group: TaskGroup,
    use_mouse_listeners: WeakSet[Callable[[Mouse], None]],
) -> Iterator[None]:
    """
    Makes one app's queue, task group and mouse listeners current for the block, then restores what was current before,
    so an app run inside another one's handler, or after it in the same task, never sees or replaces the other's.
    """
    event_queue_token = current_event_queue.set(event_queue)
    task_group_token = current_task_group.set(task_group)
    use_mouse_listeners_token = current_use_mouse_listeners.set(use_mouse_listeners)
    try:
        yield
    finally:
        current_event_queue.reset(event_queue_token)
        current_task_group.reset(task_group_token)
        current_use_mouse_listeners.reset(use_mouse_listeners_token)
