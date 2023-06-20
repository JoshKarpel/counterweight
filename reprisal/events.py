from reprisal.input import Keys
from reprisal.types import FrozenForbidExtras


class TerminalResized(FrozenForbidExtras):
    pass


class KeyPressed(FrozenForbidExtras):
    keys: tuple[Keys, ...] | str


AnyEvent = TerminalResized | KeyPressed
