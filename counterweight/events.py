from time import monotonic_ns
from typing import Union

from pydantic import Field

from counterweight.geometry import Position
from counterweight.types import FrozenForbidExtras


class Timestamped(FrozenForbidExtras):
    timestamp_ns: int = Field(default_factory=monotonic_ns)


class TerminalResized(Timestamped):
    pass


class KeyPressed(Timestamped):
    key: str


class MouseMoved(Timestamped):
    position: Position


class MouseDown(Timestamped):
    position: Position
    button: int


class MouseUp(Timestamped):
    position: Position


class StateSet(Timestamped):
    pass


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    MouseMoved,
    MouseDown,
    MouseUp,
    StateSet,
]
