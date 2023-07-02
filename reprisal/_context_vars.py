from __future__ import annotations

from contextvars import ContextVar

current_event_queue = ContextVar("current_event_queue")
current_hook_idx = ContextVar("current_hook_idx")
current_hook_state = ContextVar("current_hook_state")
