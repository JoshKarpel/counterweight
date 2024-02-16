import asyncio
from functools import lru_cache

from more_itertools import intersperse
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.events import MouseDown, MouseEvent, MouseMoved, MouseUp
from counterweight.geometry import Position
from counterweight.hooks import use_hovered, use_mouse, use_rects, use_state
from counterweight.styles import Span
from counterweight.styles.utilities import *

logger = get_logger()


BLACK = Color.from_name("black")


@lru_cache(maxsize=2**10)
def canvas_chunk(color: Color) -> Chunk:
    return Chunk(content="█", style=CellStyle(foreground=color))


def canvas(
    width: int,
    height: int,
    cells: dict[Position, Color],
) -> list[Chunk]:
    return list(
        intersperse(
            Chunk.newline(),
            (canvas_chunk(cells.get(Position.flyweight(x, y), BLACK)) for y in range(height) for x in range(width)),
            n=width,
        )
    )


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            header(),
            Div(
                style=row | gap_children_1,
                children=[
                    tracking_box(),
                    last_clicked_box(),
                    last_dragged_box(),
                ],
            ),
            Div(
                style=row | gap_children_1,
                children=[
                    drag_text_box(),
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


canvas_style = border_light | weight_none
hover_style = border_heavy | border_amber_600


@component
def tracking_box() -> Text:
    mouse = use_mouse()
    rects = use_rects()
    hovered = use_hovered()

    return Text(
        style=canvas_style | (hover_style if hovered.border else None),
        content=canvas(
            20,
            10,
            ({mouse.absolute - rects.content.top_left(): Color.from_name("red")} if hovered.content else {}),
        ),
    )


@component
def last_clicked_box() -> Text:
    rects = use_rects()
    hovered = use_hovered()

    clicked, set_clicked = use_state(Position.flyweight(0, 0))

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseUp(absolute=p, button=1):
                set_clicked(p - rects.content.top_left())

    return Text(
        on_mouse=on_mouse,
        style=canvas_style | (hover_style if hovered.border else None),
        content=canvas(
            20,
            10,
            {
                clicked: Color.from_name("green"),
            },
        ),
    )


@component
def last_dragged_box() -> Text:
    rects = use_rects()
    hovered = use_hovered()

    start, set_start = use_state(Position.flyweight(0, 0))
    end, set_end = use_state(Position.flyweight(0, 0))

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseDown(absolute=a, button=1):
                set_start(a - rects.content.top_left())
                set_end(a - rects.content.top_left())
            case MouseUp(absolute=a, button=1):
                set_end(a - rects.content.top_left())
            case MouseMoved(absolute=a, button=1):
                set_end(a - rects.content.top_left())

    return Text(
        on_mouse=on_mouse,
        style=canvas_style | (hover_style if hovered.border else None),
        content=canvas(
            20,
            10,
            {p: Color.from_name("khaki") for p in start.fill_to(end)} if start != end else {},
        ),
    )


@component
def drag_text_box() -> Div:
    hovered = use_hovered()

    return Div(
        style=canvas_style | (hover_style if hovered.border else None) | Style(span=Span(width=20, height=10)),
        children=[
            draggable_text("Drag me!", inset_top_left),
            draggable_text("No, me!", inset_bottom_right),
        ],
    )


@component
def draggable_text(content: str, start: Style) -> Text:
    mouse = use_mouse()
    offset, set_offset = use_state(Position.flyweight(0, 0))

    # TODO: if you don't slow down, your mouse can easily outrun the render speed?
    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseMoved(absolute=a, button=1):
                set_offset(lambda o: o + (a - mouse.absolute))

    return Text(
        on_mouse=on_mouse,
        style=start | absolute(x=offset.x, y=offset.y),
        content=content,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
