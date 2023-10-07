from typing import Union

from reprisal.geometry import Position
from reprisal.types import FrozenForbidExtras


class TerminalResized(FrozenForbidExtras):
    pass


class KeyPressed(FrozenForbidExtras):
    key: str


class MouseMoved(FrozenForbidExtras):
    position: Position


class MouseDown(FrozenForbidExtras):
    position: Position
    button: int


class MouseUp(FrozenForbidExtras):
    position: Position


class StateSet(FrozenForbidExtras):
    pass


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    MouseMoved,
    MouseDown,
    MouseUp,
    StateSet,
]
