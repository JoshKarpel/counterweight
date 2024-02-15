from __future__ import annotations

from dataclasses import dataclass
from typing import Union

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
    button: int | None


@dataclass(frozen=True, slots=True)
class MouseDown(_Event):
    absolute: Position
    button: int


@dataclass(frozen=True, slots=True)
class MouseUp(_Event):
    absolute: Position
    button: int


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
