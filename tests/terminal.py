from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True, slots=True)
class Terminal:
    """A pseudo-terminal: the program side reads `stream`, and the user side writes `keyboard`."""

    stream: TextIO
    keyboard: int
