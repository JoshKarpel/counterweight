import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.geometry import Position
from counterweight.hooks.hooks import use_mouse, use_state
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
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            header(),
            Div(
                style=row | gap_children_1,
                children=[
                    diff_box(),
                    tracking_box(),
                    last_clicked_box(),
                ],
            ),
        ],
    )


@component
def header() -> Text:
    return Text(
        content="Mouse Tracking Demo",
        style=text_justify_center | text_amber_600,
    )


canvas_style = border_heavy | weight_none
hover_style = border_amber_600


@component
def tracking_box() -> Text:
    mouse = use_mouse()

    return Text(
        style=canvas_style | (hover_style if mouse.hovered else None),
        content=canvas(
            30,
            15,
            {
                mouse.relative: Color.from_name("red"),
            },
        ),
    )


@component
def diff_box() -> Text:
    mouse = use_mouse()

    return Text(
        style=canvas_style | (hover_style if mouse.hovered else None),
        content=canvas(
            3,
            3,
            {
                mouse.motion + Position.flyweight(x=1, y=1): Color.from_name("purple"),
            },
        ),
    )


@component
def last_clicked_box() -> Text:
    mouse = use_mouse()
    clicked, set_clicked = use_state(Position.flyweight(0, 0))

    # TODO feels like you need a weird mix of event handling and hooks here... that is not good
    return Text(
        style=canvas_style | (hover_style if mouse.hovered else None),
        content=canvas(
            10,
            5,
            {
                clicked: Color.from_name("green"),
            },
        ),
    )


asyncio.run(app(root))
