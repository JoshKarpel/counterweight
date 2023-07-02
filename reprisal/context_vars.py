from contextvars import ContextVar

current_event_queue = ContextVar("current_event_queue")
