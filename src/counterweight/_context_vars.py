from __future__ import annotations

from asyncio import Queue
from collections.abc import Callable
from contextvars import ContextVar
from typing import TYPE_CHECKING
from weakref import WeakSet

if TYPE_CHECKING:
    from counterweight.events import AnyEvent
    from counterweight.hooks import Mouse
    from counterweight.hooks.impls import Hooks

current_event_queue: ContextVar[Queue[AnyEvent]] = ContextVar("current_event_queue")
current_use_mouse_listeners: ContextVar[WeakSet[Callable[[Mouse], None]]] = ContextVar("current_use_mouse_listeners")
current_hook_idx: ContextVar[int] = ContextVar("current_hook_idx")
current_hook_state: ContextVar[Hooks] = ContextVar("current_hook_state")
