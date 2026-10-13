from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from counterweight.controls import AnyControl
from counterweight.focus import FocusHandle, Subtree
from counterweight.geometry import Position, Rects

if TYPE_CHECKING:
    from counterweight.hooks.impls import NodeKey


@dataclass(frozen=True, slots=True)
class _Event:
    pass


@dataclass(frozen=True, slots=True)
class TerminalResized(_Event):
    dimensions: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class KeyPressed(_Event):
    key: str
    """
    The `Key` for a control or special key (`Key.Enter`, `Key.Up`, `Key.F1`),
    or the text typed: one grapheme cluster, such as `"a"`, `"é"` or `"👩‍💻"`.
    Each grapheme cluster of pasted text is its own key press.
    """


@dataclass(frozen=True, slots=True)
class MouseMoved(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: int | None
    """The button that was held during the motion, or `None` if no button was pressed."""


@dataclass(frozen=True, slots=True)
class MouseDown(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: int
    """The mouse button that was pressed during the motion."""


@dataclass(frozen=True, slots=True)
class MouseUp(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: int
    """The mouse button that was released during the motion."""


@dataclass(frozen=True, slots=True)
class MouseScrolledDown(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    direction: int = 1
    """The direction that the mouse was scrolled as an integer offset; `-1` for up, `+1` for down."""


@dataclass(frozen=True, slots=True)
class MouseScrolledUp(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    direction: int = -1
    """The direction that the mouse was scrolled as an integer offset; `-1` for up, `+1` for down."""


@dataclass(frozen=True, slots=True)
class MouseScrolledLeft(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    direction: int = -1
    """The direction that the mouse was scrolled as an integer offset; `-1` for left, `+1` for right."""


@dataclass(frozen=True, slots=True)
class MouseScrolledRight(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    direction: int = 1
    """The direction that the mouse was scrolled as an integer offset; `-1` for left, `+1` for right."""


@dataclass(frozen=True, slots=True)
class StateSet(_Event):
    key: NodeKey
    """The key of the node whose state was set."""


@dataclass(frozen=True, slots=True)
class Dummy(_Event):
    pass


MouseEvent = Union[
    MouseMoved,
    MouseDown,
    MouseUp,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseScrolledLeft,
    MouseScrolledRight,
]

InputEvent = Union[KeyPressed, MouseEvent]


@dataclass(frozen=True, slots=True)
class Receiver:
    """The element an input event is being delivered to."""

    rects: Rects
    """The receiving element's rectangles, as [`use_rects`][counterweight.hooks.use_rects] returns them."""

    is_target: bool
    """Whether the receiving element is the event's target, rather than an ancestor the event bubbled to."""

    focus_handle: FocusHandle | None
    """
    The [`FocusHandle`][counterweight.focus.FocusHandle] of the receiving element's component,
    if the element is the one its component returned and the component called
    [`use_focus`][counterweight.hooks.use_focus], or `None`.
    """

    is_focused: bool
    """
    Whether the receiving element is the focused one.
    For a key press it's the same as `is_target`, except when nothing is focused:
    the root component's element is then the target, and no receiver is focused.
    """

    subtree: Subtree
    """
    The receiving element and its descendants,
    for [`FocusNext`][counterweight.controls.FocusNext] and [`FocusPrevious`][counterweight.controls.FocusPrevious]
    to move focus within.
    """

    def relative(self, position: Position) -> Position:
        """`position` relative to the top-left corner of the receiving element's content box."""
        return position - self.rects.content.top_left


InputResponse = Union[AnyControl, tuple[AnyControl | None, ...], None]

InputHandler = Callable[[InputEvent, Receiver], InputResponse]


def response_controls(response: InputResponse) -> tuple[AnyControl, ...] | None:
    """
    The controls a handler's `response` holds, skipping any `None` in a tuple,
    or `None` if the handler didn't handle the event.
    """
    match response:
        case None:
            return None
        case tuple():
            return tuple(control for control in response if control is not None)
        case _:
            return (response,)


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    StateSet,
    MouseEvent,
    Dummy,
]
