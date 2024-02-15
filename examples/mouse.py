import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.geometry import Position
from counterweight.hooks.hooks import use_mouse
from counterweight.styles.utilities import *

logger = get_logger()


BLACK = Color.from_name("black")


def canvas(
    width: int,
    height: int,
    cells: dict[Position, Color],
) -> list[Chunk]:
    c: list[Chunk] = []
    for y in range(height):
        c.extend(
            Chunk(
                content="█",
                style=CellStyle(
                    foreground=cells.get(Position.flyweight(x, y), BLACK),
                ),
            )
            for x in range(width)
        )
        c.append(Chunk.newline())
    return c[:-1]  # strip off last newline


@component
def root() -> Div:
    pos = use_mouse()

    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            Div(
                style=border_heavy,
                children=[
                    Text(
                        content=canvas(
                            50,
                            25,
                            {pos: Color.from_name("cyan")},
                        )
                    ),
                ],
            )
        ],
    )


asyncio.run(app(root))
