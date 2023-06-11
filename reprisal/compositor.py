from dataclasses import dataclass
from typing import Dict

from reprisal.elements import Div


@dataclass(frozen=True)
class ScreenSize:
    width: int
    height: int


def composite(root: Div, screen_size: ScreenSize) -> Dict[tuple[int, int], str]:
    pass

    # something about chainmaps/merging/layering
    # keys are cell positions on the screen
    # values are the character to display, plus the instructions about which control codes to write for
    # things like foreground/background/bold/whatever
    # another module is responsible for finding runs of characters for efficient printing!
    # this should be a fully static and self-contained map of each character to put on the screen and each of their styles
