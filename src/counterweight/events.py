from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from counterweight.controls import AnyControl
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Scroll

if TYPE_CHECKING:
    from counterweight.hooks._impls import NodeKey


@dataclass(frozen=True, slots=True)
class _Event:
    pass


@dataclass(frozen=True, slots=True)
class TerminalResized(_Event):
    """
    The terminal changed size, so the app lays out and draws the whole screen again.
    The app sends itself one when the terminal reports a resize, and an autopilot can send one to resize a headless app.
    """

    dimensions: tuple[int, int] | None = None
    """
    The new size, as `(width, height)` in cells,
    or `None` for the size the app was given as its `dimensions`, or else the terminal's size.
    """


@dataclass(frozen=True, slots=True)
class KeyPressed(_Event):
    """A key press, which goes to the focused element, or the root component's element when nothing is focused."""

    key: str
    """
    The `Key` for a control or special key (`Key.Enter`, `Key.Up`, `Key.F1`), or for one pressed with Alt
    (`Key.AltEnter`, `Key.AltUp`, `Key.ControlAltA`),
    the text typed: one grapheme cluster, such as `"a"`, `"é"` or `"👩‍💻"`,
    or `alt+` and the text, for text typed with Alt, such as `"alt+b"` or `"alt+B"` (Alt with Shift and B).
    Text pasted in a terminal without bracketed paste arrives as a key press per grapheme cluster;
    in one with it, the text arrives as one [`Pasted`][counterweight.events.Pasted].
    """


@dataclass(frozen=True, slots=True)
class Pasted(_Event):
    """Text pasted into the terminal, which goes where a key press would."""

    text: str
    """
    The text pasted into the terminal, whole, with each line break as `"\\n"`
    (terminals send a pasted line break as a carriage return).
    It can hold anything a key press can't, such as line breaks and tabs, which arrive as text rather than as keys.
    """


@dataclass(frozen=True, slots=True)
class MouseMoved(_Event):
    """The mouse moved, with or without a button held."""

    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: int | None
    """The button that was held during the motion, or `None` if no button was pressed."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseDown(_Event):
    """A mouse button went down."""

    absolute: Position
    """The absolute position on the screen where the button went down."""

    button: int
    """The mouse button that went down: 1 is the primary button, 2 the middle, and 3 the secondary."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseUp(_Event):
    """A mouse button came up."""

    absolute: Position
    """The absolute position on the screen where the button came up."""

    button: int
    """The mouse button that came up: 1 is the primary button, 2 the middle, and 3 the secondary."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseScrolledDown(_Event):
    """The mouse wheel turned one step down."""

    absolute: Position
    """The absolute position on the screen of the pointer as the wheel turned."""

    direction: int = 1
    """The direction that the mouse was scrolled as an integer offset; `-1` for up, `+1` for down."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseScrolledUp(_Event):
    """The mouse wheel turned one step up."""

    absolute: Position
    """The absolute position on the screen of the pointer as the wheel turned."""

    direction: int = -1
    """The direction that the mouse was scrolled as an integer offset; `-1` for up, `+1` for down."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseScrolledLeft(_Event):
    """The mouse wheel turned one step left, as a trackpad's sideways swipe does."""

    absolute: Position
    """The absolute position on the screen of the pointer as the wheel turned."""

    direction: int = -1
    """The direction that the mouse was scrolled as an integer offset; `-1` for left, `+1` for right."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class MouseScrolledRight(_Event):
    """The mouse wheel turned one step right, as a trackpad's sideways swipe does."""

    absolute: Position
    """The absolute position on the screen of the pointer as the wheel turned."""

    direction: int = 1
    """The direction that the mouse was scrolled as an integer offset; `-1` for left, `+1` for right."""

    is_shift_held: bool = False
    """Whether Shift was held, as the DOM's `MouseEvent.shiftKey` reports it."""

    is_alt_held: bool = False
    """Whether Alt (Option on macOS) was held, as the DOM's `MouseEvent.altKey` reports it."""

    is_control_held: bool = False
    """Whether Control was held, as the DOM's `MouseEvent.ctrlKey` reports it."""


@dataclass(frozen=True, slots=True)
class StateSet(_Event):
    key: NodeKey
    """The key of the node whose state was set."""


@dataclass(frozen=True, slots=True)
class ControlSent(_Event):
    control: AnyControl
    """The control a [`use_controls`][counterweight.hooks.use_controls] sender sent, which the app handles as it
    handles a control an input handler returns."""


@dataclass(frozen=True, slots=True)
class Dummy(_Event):
    pass


MouseEvent = (
    MouseMoved | MouseDown | MouseUp | MouseScrolledDown | MouseScrolledUp | MouseScrolledLeft | MouseScrolledRight
)
"""Any mouse event, which goes to the element drawn on top at the pointer, unless a press has captured the mouse."""

InputEvent = KeyPressed | Pasted | MouseEvent
"""Any event an input handler receives."""


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
    For a key press or a paste it's the same as `is_target`, except when nothing is focused:
    the root component's element is then the target, and no receiver is focused.
    """

    subtree: Subtree
    """
    The receiving element and its descendants,
    for [`FocusNext`][counterweight.controls.FocusNext] and [`FocusPrevious`][counterweight.controls.FocusPrevious]
    to move focus within, for [`ScrollTo`][counterweight.controls.ScrollTo]
    and [`ScrollBy`][counterweight.controls.ScrollBy] to scroll it,
    and for [`ScrollIntoView`][counterweight.controls.ScrollIntoView] to bring it into view.
    """

    scroll: Scroll | None
    """
    How far the receiving element is scrolled, if it's a scroll container, or `None` if it isn't:
    its scroll as of the last render, as [`use_scroll`][counterweight.hooks.use_scroll] reports it,
    moved by each [`ScrollTo`][counterweight.controls.ScrollTo] and [`ScrollBy`][counterweight.controls.ScrollBy]
    returned since, and clamped to its range as of that render,
    so a handler later in a batch of input sees what the ones before it scrolled.
    """

    def relative(self, position: Position) -> Position:
        """`position` relative to the top-left corner of the receiving element's content box."""
        return position - self.rects.content.top_left


InputResponse = AnyControl | tuple[AnyControl | None, ...] | None
"""
What an input handler returns: `None` to pass the event on to the element's parent,
or a control or a tuple of controls to stop it there and have the app apply them in order, skipping any `None`,
with `()` to stop it with nothing more to do.
"""

InputHandler = Callable[[InputEvent, Receiver], InputResponse]
"""An element's `on_input`: what it does with an input event that reaches it, given the element as a `Receiver`."""


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


AnyEvent = TerminalResized | KeyPressed | Pasted | StateSet | ControlSent | MouseEvent | Dummy
"""Any event the app handles, which an autopilot can send it beside controls."""


__all__ = [
    "AnyEvent",
    "InputEvent",
    "InputHandler",
    "InputResponse",
    "KeyPressed",
    "MouseDown",
    "MouseEvent",
    "MouseMoved",
    "MouseScrolledDown",
    "MouseScrolledLeft",
    "MouseScrolledRight",
    "MouseScrolledUp",
    "MouseUp",
    "Pasted",
    "Receiver",
    "TerminalResized",
    "response_controls",
]
