import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

WARNING = text_bold | text_color("amber", 400)
ASIDE = text_italic | text_dim


@component
def root() -> Div:
    return Div(
        style=col | gap(1) | pad_x(1),
        children=(
            Text(
                content=(
                    Chunk(content="warning: ", style=WARNING),
                    Chunk(content="3 tests were "),
                    Chunk(content="skipped", style=text_underline | text_color(rose_400)),
                    Chunk(content=" (run with -v to see why)", style=ASIDE),
                ),
                style=text_wrap_pretty,
            ),
            Text(
                content=(
                    Chunk(content="This whole Text is bold and sky blue, "),
                    Chunk(content="except this", style=text_not_bold | text_color("slate", 400)),
                    Chunk(content="."),
                ),
                style=text_bold | text_color("sky", 300) | text_wrap_pretty,
            ),
        ),
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root(), "text-chunks", (64, 3))]


if __name__ == "__main__":
    asyncio.run(app(root()))
