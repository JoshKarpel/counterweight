import termios
from dataclasses import dataclass
from typing import TextIO

from counterweight.input import LFLAG, TCGetAttr


@dataclass(frozen=True, slots=True)
class Terminal:
    """A pseudo-terminal: the program side reads `stream`, and the user side writes `keyboard`."""

    stream: TextIO
    keyboard: int

    def settings(self) -> TCGetAttr:
        """
        The program side's attributes, as `termios.tcgetattr` reads them, less the `PENDIN` state bit.
        macOS sets `PENDIN` whenever line buffering is turned back on, and clears it only on the next read,
        so restoring the original attributes can't restore it.
        """
        attributes = termios.tcgetattr(self.stream)
        attributes[LFLAG] &= ~termios.PENDIN
        return attributes
