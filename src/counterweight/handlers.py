"""
Library input handlers for behaviors that apps compose onto their elements,
and the combinators that compose several handlers into the one an element takes.
Each is a pure function of an event and a receiver, so it can be tested without running an app.
"""

from __future__ import annotations

from collections.abc import Callable

from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    MouseDown,
    MouseMoved,
    MouseUp,
    Receiver,
    response_controls,
)


def first(*handlers: InputHandler) -> InputHandler:
    """
    A handler that calls each of `handlers` in turn with the same event and receiver,
    and returns the first response that isn't `None`, `()` included, without calling the rest.
    It returns `None` if none of them responds.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        for inner in handlers:
            if (response := inner(event, receiver)) is not None:
                return response
        return None

    return handler


def each(*handlers: InputHandler) -> InputHandler:
    """
    A handler that calls every one of `handlers` with the same event and receiver.
    If any responds with something other than `None`,
    it returns a tuple of every control they returned, in the order of `handlers`,
    which is `()` if every response was `()`.
    It returns `None` if none of them responds.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        responses = [response_controls(inner(event, receiver)) for inner in handlers]
        if all(response is None for response in responses):
            return None
        return tuple(control for response in responses for control in response or ())

    return handler


def on_click(action: Callable[[], InputResponse]) -> InputHandler:
    """
    A handler that claims a button `1` `MouseDown`, and so every later event of the press,
    and on the press's `MouseUp`, calls `action` if the release is inside the element's border box.
    It returns the controls `action` returns, or `()` if `action` returns `None`.
    It returns `None` for anything else, such as a key or a pointer move with no button held.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(button=1) | MouseMoved(button=1):
                return ()
            case MouseUp(absolute=position, button=1):
                if not receiver.rects.border.contains(position):
                    return ()
                response = action()
                return () if response is None else response
            case _:
                return None

    return handler
