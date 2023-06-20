from reprisal.types import FrozenForbidExtras


class TerminalResized(FrozenForbidExtras):
    pass


class KeyPressed(FrozenForbidExtras):
    key: str


class MouseMoved(FrozenForbidExtras):
    x: int
    y: int


AnyEvent = TerminalResized | KeyPressed | MouseMoved
