from __future__ import annotations

from asyncio import Queue
from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    from counterweight.components import Component
    from counterweight.events import AnyEvent
    from counterweight.hooks import Mouse
    from counterweight.hooks.impls import Hooks
    from counterweight.layout import Layouts

current_event_queue: ContextVar[Queue[AnyEvent]] = ContextVar("current_event_queue")
current_use_mouse_listeners: ContextVar[WeakSet[Callable[[Mouse], None]]] = ContextVar("current_use_mouse_listeners")
current_hook_idx: ContextVar[int] = ContextVar("current_hook_idx")
current_hook_state: ContextVar[Hooks] = ContextVar("current_hook_state")
current_layouts: ContextVar[Layouts] = ContextVar("current_layouts")
# The component being called when `check_purity` is on, so `use_memo` can check its cached values and name it.
current_purity_checked: ContextVar[Component | None] = ContextVar("current_purity_checked", default=None)
