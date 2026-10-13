import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.styles import CellStyle
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

LINK = CellStyle(underline=True) | text_color("sky", 300).text_style


@component
def root() -> Div:
    return Div(
        style=col | gap(1) | pad_x(1),
        children=[
            Text(
                content=[
                    Chunk(content="Counterweight is on "),
                    Chunk(content="GitHub", style=LINK | CellStyle(link="https://github.com/JoshKarpel/counterweight")),
                    Chunk(content=", and its docs are at "),
                    Chunk(content="counterweight.dev", style=LINK | CellStyle(link="https://www.counterweight.dev")),
                    Chunk(content="."),
                ],
                style=text_wrap_pretty,
            ),
            Text(
                content="This whole Text is one link.",
                style=pad_x(1)
                | border
                | border_lightrounded
                | Style(text_style=CellStyle(link="https://pygments.org")),
            ),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root(), "hyperlinks", (50, 7))]


if __name__ == "__main__":
    asyncio.run(app(root()))
