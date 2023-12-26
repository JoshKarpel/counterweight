from time import monotonic_ns
from typing import Union

from pydantic import Field

from counterweight.geometry import Position
from counterweight.types import FrozenForbidExtras


class _Timestamped(FrozenForbidExtras):
    timestamp_ns: int = Field(default_factory=monotonic_ns)


class TerminalResized(_Timestamped):
    pass


class KeyPressed(_Timestamped):
    key: str


class MouseMoved(_Timestamped):
    position: Position


class MouseDown(_Timestamped):
    position: Position
    button: int


class MouseUp(_Timestamped):
    position: Position


class StateSet(_Timestamped):
    pass


AnyEvent = Union[
    TerminalResized,
    KeyPressed,
    MouseMoved,
    MouseDown,
    MouseUp,
    StateSet,
]
