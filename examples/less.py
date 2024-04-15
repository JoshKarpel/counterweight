import asyncio
import sys
from pathlib import Path

from structlog import get_logger

from counterweight._utils import clamp
from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_rects, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()


@component
def root(initial_path: Path) -> Div:
    text, set_text = use_state(initial_path.read_text)

    def on_key(e: KeyPressed) -> None:
        pass

    return Div(
        style=col | align_self_stretch,
        on_key=on_key,
        children=[
            file_viewer(text),
        ],
    )


@component
def file_viewer(text: str) -> Text:
    x, set_x = use_state(0)
    y, set_y = use_state(0)

    rects = use_rects()

    # TODO: maybe you can pass a text a callable?
    # in layout we'll assume its as tall and wide as possible,
    # then call the callable with those dimensions

    def on_key(e: KeyPressed) -> None:
        # TODO scroll limits
        match e.key:
            case Key.Down:
                set_y(lambda o: clamp(0, o + 1, None))
            case "d":
                set_y(lambda o: clamp(0, o + rects.content.height, None))
            case Key.Up:
                set_y(lambda o: clamp(0, o - 1, None))
            case "u":
                set_y(lambda o: clamp(0, o - rects.content.height, None))
            case "g":
                set_y(0)
            case "G":
                pass  # TODO: jump to end
            case Key.Right:
                set_x(lambda o: clamp(0, o + 1, None))
            case Key.Left:
                set_x(lambda o: clamp(0, o - 1, None))

    return Text(
        style=align_self_stretch,
        on_key=on_key,
        content=text,
        offset=(x, y),
    )


if __name__ == "__main__":
    file = Path(sys.argv[1])
    asyncio.run(app(root, file))
