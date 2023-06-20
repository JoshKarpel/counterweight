from string import printable

from reprisal.types import FrozenForbidExtras


class TerminalResized(FrozenForbidExtras):
    pass


class KeyPressed(FrozenForbidExtras):
    key: str

    @property
    def printable(self) -> bool:
        return self.key in printable


class MouseMoved(FrozenForbidExtras):
    x: int
    y: int


AnyEvent = TerminalResized | KeyPressed
