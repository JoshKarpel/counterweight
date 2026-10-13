from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from counterweight.geometry import Position

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
]

AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    StateSet,
    MouseMoved,
    MouseDown,
    MouseUp,
    MouseScrolledDown,
    MouseScrolledUp,
    Dummy,
]
