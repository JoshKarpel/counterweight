import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:places]

PLACES: tuple[tuple[str, ColorName, Shade], ...] = (
    ("margin_color", "indigo", 900),
    ("border_color", "amber", 400),
    ("border_bg", "slate", 600),
    ("padding_color", "teal", 700),
    ("content_color", "rose", 900),
    ("text_color", "lime", 300),
    ("text_bg", "sky", 800),
)


def legend_line(utility: str, color: ColorName, shade: Shade) -> Text:
    return Text(
        content=(
            Chunk(content="██ ", style=text_color(color, shade).text_style),
            Chunk(content=f'{utility}("{color}", {shade})'),
        )
    )


@component
def places() -> Div:
    return Div(
        style=row | gap(2) | align_children_center,
        children=(
            Div(
                style=width(26)
                | height(7)
                | center_children
                | margin(1)
                | margin_color("indigo", 900)
                | border
                | border_heavy
                | border_color("amber", 400)
                | border_bg("slate", 600)
                | pad_x(2)
                | pad_y(1)
                | padding_color("teal", 700)
                | content_color("rose", 900),
                children=(Text(style=text_color("lime", 300) | text_bg("sky", 800), content="Some text"),),
            ),
            Div(style=col, children=tuple(legend_line(*place) for place in PLACES)),
        ),
    )


# --8<-- [end:places]

# --8<-- [start:terminal]


def swatch(index: int) -> Text:
    return Text(style=text_bg_indexed(index) | width(6) | text_justify_center, content=str(index))


@component
def terminal_colors() -> Div:
    return Div(
        style=col,
        children=(
            Div(style=row, children=tuple(swatch(index) for index in range(8))),
            Div(style=row, children=tuple(swatch(index) for index in range(8, 16))),
            Text(
                style=text_terminal_default | text_bg_terminal_default | margin_top(1) | pad_x(1),
                content="text_terminal_default | text_bg_terminal_default",
            ),
        ),
    )


# --8<-- [end:terminal]

SCREENSHOTS = [
    ScreenshotSpec(places(), "styles-color-places", (60, 9)),
    ScreenshotSpec(terminal_colors(), "styles-terminal-colors", (50, 4)),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (places, terminal_colors)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else places()))
