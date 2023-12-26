from time import monotonic_ns
from typing import Union

from pydantic import Field

from counterweight.geometry import Position
from counterweight.types import FrozenForbidExtras


class _Event(FrozenForbidExtras):
    timestamp_ns: int = Field(default_factory=monotonic_ns)


class TerminalResized(_Event):
    pass


class KeyPressed(_Event):
    key: str


class MouseMoved(_Event):
    position: Position


class MouseDown(_Event):
    position: Position
    button: int


class MouseUp(_Event):
    position: Position


class StateSet(_Event):
    pass


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    MouseMoved,
    MouseDown,
    MouseUp,
    StateSet,
]
