import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:chunks]


@component
def chunks() -> Div:
    return Div(
        style=col,
        children=(
            Text(content="A plain string, in the Text's text_style", style=text_color("slate", 300)),
            Text(
                style=text_color("slate", 300),
                content=(
                    Chunk(content="error", style=CellStyle(foreground=red_500, bold=True)),
                    Chunk(content=": "),
                    Chunk(content="config.toml", style=CellStyle(underline=True)),
                    Chunk(content=" not found"),
                ),
            ),
        ),
    )


# --8<-- [end:chunks]

# --8<-- [start:wide]

WIDE = "日本語の文章 👩‍💻 🇯🇵"


def pane(label: str, text_style: Style, content_width: int) -> Div:
    return Div(
        style=col | width(content_width + 2),
        children=(
            Text(content=label),
            Div(style=col | border, children=(Text(style=text_style, content=WIDE),)),
        ),
    )


@component
def wide() -> Div:
    return Div(
        style=row | align_children_start | gap(2),
        children=(
            pane("wraps", text_wrap_stable, 10),
            pane("clipped", overflow_hidden, 9),
            pane("overflows", default, 9),
        ),
    )


# --8<-- [end:wide]

# --8<-- [start:control]


@component
def control() -> Text:
    return Text(content="name\tsize\nnotes.txt\t\x1b[31mred?\x1b[0m\r\nend\x07")


# --8<-- [end:control]

SCREENSHOTS = [
    ScreenshotSpec(chunks(), "elements-text-chunks", (42, 2)),
    ScreenshotSpec(wide(), "elements-text-wide", (48, 6)),
    ScreenshotSpec(control(), "elements-text-control", (24, 3)),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (chunks, wide, control)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else chunks()))
