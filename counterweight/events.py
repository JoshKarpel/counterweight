from dataclasses import dataclass
from typing import Union

from counterweight.geometry import Position


@dataclass(frozen=True)
class _Event:
    pass


@dataclass(frozen=True)
class TerminalResized(_Event):
    pass


@dataclass(frozen=True)
class KeyPressed(_Event):
    key: str


@dataclass(frozen=True)
class MouseMoved(_Event):
    position: Position
    button: int | None


@dataclass(frozen=True)
class MouseDown(_Event):
    position: Position
    button: int


@dataclass(frozen=True)
class MouseUp(_Event):
    position: Position
    button: int


@dataclass(frozen=True)
class StateSet(_Event):
    pass


@dataclass(frozen=True)
class Dummy(_Event):
    pass


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    MouseMoved,
    MouseDown,
    MouseUp,
    StateSet,
    Dummy,
]
