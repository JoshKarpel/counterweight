import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.highlighting import code_block
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

SOURCE = '''\
@component
def greeting(name: str) -> Text:
    """Say hello."""
    return Text(content=f"Hello, {name}!")
'''


@component
def root() -> Div:
    return Div(
        style=col | gap(1),
        children=[
            Div(
                style=col,
                children=[
                    Text(content=f" {theme} ", style=text_color("slate", 400)),
                    code_block(SOURCE.rstrip("\n"), "python", theme=theme, style=pad(1)),
                ],
            )
            for theme in ("github-dark", "monokai", "solarized-light")
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root(), "syntax-highlighting", (50, 24))]


if __name__ == "__main__":
    asyncio.run(app(root()))
