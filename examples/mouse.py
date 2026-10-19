import asyncio
import logging
from collections.abc import Iterable

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.geometry import Position
from counterweight.geometry import Region
from counterweight.hooks import Ref
from counterweight.hooks import use_hovered
from counterweight.hooks import use_mouse
from counterweight.hooks import use_rects
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.painters.pixels import HalfBlocks
from counterweight.painters.pixels import Pixels
from counterweight.styles import Color
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


# 20x20 pixels, which half blocks draw in 20x10 cells.
BLANK = Pixels.blank(20, 20, Color.from_name("black"))


def painted(cells: Iterable[Position], color: Color, box: Region) -> HalfBlocks:
    """The blank picture with both of the pixels in each of `cells` of a canvas whose content box is `box` set to `color`."""
    blank = HalfBlocks(BLANK)
    pixels = {pixel: color for cell in cells for pixel in blank.pixels_at(cell, box.width, box.height)}
    return HalfBlocks(BLANK.with_points(pixels))


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=(
            header(),
            Div(
                style=row | gap(1),
                children=(
                    tracking_box(),
                    last_clicked_box(),
                    last_dragged_box(),
                ),
            ),
            Div(
                style=row | gap(1),
                children=(drag_text_box(),),
            ),
        ),
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
def tracking_box() -> Canvas:
    mouse = use_mouse()
    rects = use_rects()
    hovered = use_hovered()

    return Canvas(
        style=canvas_style | (hover_style if hovered.border else None),
        painter=painted(
            [mouse.absolute - rects.content.top_left] if hovered.content else [],
            Color.from_name("red"),
            rects.content,
        ),
    )


@component
def last_clicked_box() -> Canvas:
    rects = use_rects()
    hovered = use_hovered()

    clicked, set_clicked = use_state(Position(0, 0))

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=p, button=1):
                set_clicked(receiver.relative(p))
                return ()
            case _:
                return None

    return Canvas(
        on_input=on_input,
        style=canvas_style | (hover_style if hovered.border else None),
        painter=painted([clicked], Color.from_name("green"), rects.content),
    )


@component
def last_dragged_box() -> Canvas:
    rects = use_rects()
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

    return Canvas(
        on_input=on_input,
        style=canvas_style | (hover_style if hovered.border else None),
        painter=painted(start.fill_to(end) if start != end else [], Color.from_name("khaki"), rects.content),
    )


@component
def drag_text_box() -> Div:
    hovered = use_hovered()

    return Div(
        style=canvas_style | (hover_style if hovered.border else None) | size(20, 10),
        children=(
            draggable_text("Drag me!", 0, 0),
            draggable_text("No, me!", 8, 5),
        ),
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
    asyncio.run(app(root()))
