from reprisal.geometry import Position
from reprisal.types import FrozenForbidExtras


class TerminalResized(FrozenForbidExtras):
    pass


class KeyPressed(FrozenForbidExtras):
    key: str


class MouseMoved(FrozenForbidExtras):
    position: Position


class StateSet(FrozenForbidExtras):
    pass


AnyEvent = TerminalResized | KeyPressed | MouseMoved | StateSet
