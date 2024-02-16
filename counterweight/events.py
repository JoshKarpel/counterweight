from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from counterweight.geometry import Position


@dataclass(frozen=True, slots=True)
class _Event:
    pass


@dataclass(frozen=True, slots=True)
class TerminalResized(_Event):
    pass


@dataclass(frozen=True, slots=True)
class KeyPressed(_Event):
    key: str


@dataclass(frozen=True, slots=True)
class MouseMoved(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: Literal[1, 2, 3] | None
    """The button that was held during the motion, or `None` if no button was pressed."""


@dataclass(frozen=True, slots=True)
class MouseDown(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: Literal[1, 2, 3]
    """The mouse button that was pressed during the motion."""


@dataclass(frozen=True, slots=True)
class MouseUp(_Event):
    absolute: Position
    """The absolute position on the screen that the mouse moved to."""

    button: Literal[1, 2, 3]
    """The mouse button that was released during the motion."""


@dataclass(frozen=True, slots=True)
class StateSet(_Event):
    pass


@dataclass(frozen=True, slots=True)
class Dummy(_Event):
    pass


MouseEvent = Union[
    MouseMoved,
    MouseDown,
    MouseUp,
]

AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    StateSet,
    MouseMoved,
    MouseDown,
    MouseUp,
    Dummy,
]
