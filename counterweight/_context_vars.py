from __future__ import annotations

from asyncio import Queue
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from counterweight._utils import TeeQueue
    from counterweight.events import AnyEvent, MouseEvent
    from counterweight.hooks.impls import Hooks

current_event_queue: ContextVar[Queue[AnyEvent]] = ContextVar("current_event_queue")
current_mouse_event_queue: ContextVar[TeeQueue[MouseEvent]] = ContextVar("current_mouse_event_queue")
current_hook_idx: ContextVar[int] = ContextVar("current_hook_idx")
current_hook_state: ContextVar[Hooks] = ContextVar("current_hook_state")
