import asyncio

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Chunk, Div, Text, component
from reprisal.styles.utilities import *

logger = get_logger()


@component
def root() -> Div:
    return Div(
        style=col | align_children_center,
        children=[
            Text(
                content=[
                    Chunk(
                        content="Canvas",
                        style=text_amber_600.typography.style,
                    ),
                    Chunk.space(),
                    Chunk(
                        content="Demo",
                        style=text_cyan_600.typography.style,
                    ),
                    Chunk.newline(),
                    Chunk(
                        content="App",
                        style=text_pink_300.typography.style,
                    ),
                ],
                style=border_heavy | border_slate_400 | pad_x_2 | pad_y_1 | text_justify_center,
            ),
        ],
    )


asyncio.run(app(root))
