import asyncio
import logging
from functools import lru_cache

from more_itertools import intersperse

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, MouseDown, MouseMoved, MouseUp, Receiver
from counterweight.geometry import Position
from counterweight.hooks import Ref, use_hovered, use_mouse, use_rects, use_ref, use_state
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


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
            (canvas_chunk(cells.get(Position(x, y), BLACK)) for y in range(height) for x in range(width)),
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
                style=row | gap(1),
                children=[
                    tracking_box(),
                    last_clicked_box(),
                    last_dragged_box(),
                ],
            ),
            Div(
                style=row | gap(1),
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
        style=text_justify_center | text_color("amber", 600),
    )


canvas_style = border
hover_style = border | border_heavy | border_color("amber", 600)


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
            ({mouse.absolute - rects.content.top_left: Color.from_name("red")} if hovered.content else {}),
        ),
    )


@component
def last_clicked_box() -> Text:
    hovered = use_hovered()

    clicked, set_clicked = use_state(Position(0, 0))

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=p, button=1):
                set_clicked(receiver.relative(p))
                return ()
            case _:
                return None

    return Text(
        on_input=on_input,
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
    hovered = use_hovered()

    start, set_start = use_state(Position(0, 0))
    end, set_end = use_state(Position(0, 0))

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=a, button=1):
                set_start(receiver.relative(a))
                set_end(receiver.relative(a))
                return ()
            case MouseUp(absolute=a, button=1) | MouseMoved(absolute=a, button=1):
                set_end(receiver.relative(a))
                return ()
            case _:
                return None

    return Text(
        on_input=on_input,
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
        style=canvas_style | (hover_style if hovered.border else None) | size(20, 10),
        children=[
            draggable_text("Drag me!", 0, 0),
            draggable_text("No, me!", 8, 5),
        ],
    )


@component
def draggable_text(content: str, init_x: int, init_y: int) -> Text:
    offset, set_offset = use_state(Position(init_x, init_y))
    # See docs/cookbook/draggable-components.md for why this is a ref, and why each move sets an absolute offset.
    grab: Ref[tuple[Position, Position] | None] = use_ref(None)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=a, button=1):
                grab.current = (a, offset)
                return ()
            case MouseMoved(absolute=a, button=1) if grab.current is not None:
                pointer, start = grab.current
                set_offset(start + (a - pointer))
                return ()
            case _:
                return None

    return Text(
        on_input=on_input,
        style=position_absolute | inset_left(offset.x) | inset_top(offset.y),
        content=content,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
