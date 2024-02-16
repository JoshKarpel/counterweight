import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.events import MouseDown, MouseEvent, MouseMoved, MouseUp
from counterweight.geometry import Position
from counterweight.hooks.hooks import use_mouse, use_rects, use_state
from counterweight.styles import Span
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

    return Text(
        style=canvas_style | (hover_style if mouse.absolute in rects.border else None),
        content=canvas(
            20,
            10,
            (
                {mouse.absolute - rects.content.top_left(): Color.from_name("red")}
                if mouse.absolute in rects.content
                else {}
            ),
        ),
    )


@component
def last_clicked_box() -> Text:
    mouse = use_mouse()
    rects = use_rects()

    clicked, set_clicked = use_state(Position.flyweight(0, 0))

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseUp(absolute=p):
                set_clicked(p - rects.content.top_left())

    return Text(
        on_mouse=on_mouse,
        style=canvas_style | (hover_style if mouse.absolute in rects.border else None),
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
    mouse = use_mouse()
    rects = use_rects()

    start, set_start = use_state(None)
    end, set_end = use_state(None)

    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseDown(absolute=a):
                set_start(a - rects.content.top_left())
                set_end(None)
            case MouseUp(absolute=a):
                set_end(a - rects.content.top_left())
            case MouseMoved(absolute=a, button=b) if b is not None:
                set_end(a - rects.content.top_left())

    return Text(
        on_mouse=on_mouse,
        style=canvas_style | (hover_style if mouse.absolute in rects.border else None),
        content=canvas(20, 10, {p: Color.from_name("khaki") for p in start.fill_to(end)} if start and end else {}),
    )


@component
def drag_text_box() -> Div:
    mouse = use_mouse()
    rects = use_rects()

    parent_content_top_left = rects.content.top_left()

    return Div(
        style=canvas_style
        | (hover_style if mouse.absolute in rects.border else None)
        | Style(span=Span(width=20, height=10)),
        children=[
            draggable_text("Drag me!", inset_top_left, parent_content_top_left),
            draggable_text("No, me!", inset_bottom_right, parent_content_top_left),
        ],
    )


@component
def draggable_text(content: str, start: Style, parent_content_top_left: Position) -> Text:
    position, set_position = use_state(Position.flyweight(0, 0))

    # TODO: if you don't slow down, your mouse can easily outrun the render speed?
    # TODO: this makes the "top left corner" draggable, it always snaps to that, so we do still want something more like a diff here
    # TODO: also this doesn't work with the "starting inset" technique below
    def on_mouse(event: MouseEvent) -> None:
        match event:
            case MouseMoved(absolute=a, button=b) if b is not None:
                set_position(a - parent_content_top_left)

    return Text(
        on_mouse=on_mouse,
        style=start | absolute(x=position.x, y=position.y),
        content=content,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
