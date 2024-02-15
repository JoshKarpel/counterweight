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
class MouseMovedRaw(_Event):
    position: Position
    button: int | None

    def relative_to(self, position: Position) -> MouseMoved:
        return MouseMoved(
            position=self.position,
            button=self.button,
            relative=self.position - position,
        )


@dataclass(frozen=True, slots=True)
class MouseMoved(MouseMovedRaw):
    relative: Position


@dataclass(frozen=True, slots=True)
class MouseDownRaw(_Event):
    position: Position
    button: int

    def relative_to(self, position: Position) -> MouseDown:
        return MouseDown(
            position=self.position,
            button=self.button,
            relative=self.position - position,
        )


@dataclass(frozen=True, slots=True)
class MouseDown(MouseDownRaw):
    relative: Position


@dataclass(frozen=True, slots=True)
class MouseUpRaw(_Event):
    position: Position
    button: int

    def relative_to(self, position: Position) -> MouseUp:
        return MouseUp(
            position=self.position,
            button=self.button,
            relative=self.position - position,
        )


@dataclass(frozen=True, slots=True)
class MouseUp(MouseUpRaw):
    relative: Position


@dataclass(frozen=True, slots=True)
class StateSet(_Event):
    pass


@dataclass(frozen=True, slots=True)
class Dummy(_Event):
    pass


RawMouseEvent = Union[
    MouseMovedRaw,
    MouseDownRaw,
    MouseUpRaw,
]

MouseEvent = Union[
    MouseMoved,
    MouseDown,
    MouseUp,
]

AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    StateSet,
    MouseMovedRaw,
    MouseMoved,
    MouseDownRaw,
    MouseDown,
    MouseUpRaw,
    MouseUp,
    Dummy,
]
