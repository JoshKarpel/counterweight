import asyncio
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, MouseDown, MouseMoved, MouseUp, Receiver
from counterweight.geometry import Position, Region
from counterweight.hooks import Ref, use_rects, use_ref, use_state
from counterweight.styles.utilities import *
from counterweight.utils import clamp
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@dataclass(frozen=True, slots=True)
class Grab:
    pointer: Position
    offset: Position


@component
def draggable(content: str, start: Position, bounds: Region) -> Text:
    offset, set_offset = use_state(start)
    grab: Ref[Grab | None] = use_ref(None)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=pointer, button=1):
                grab.current = Grab(pointer=pointer, offset=offset)
                return ()
            case MouseMoved(absolute=pointer, button=1) if grab.current is not None:
                target = grab.current.offset + (pointer - grab.current.pointer)
                box = receiver.rects.border
                set_offset(
                    Position(
                        x=clamp(0, target.x, bounds.width - box.width),
                        y=clamp(0, target.y, bounds.height - box.height),
                    )
                )
                return ()
            case MouseUp(button=1):
                grab.current = None
                return ()
            case _:
                return None

    return Text(
        content=content,
        on_input=on_input,
        style=position_absolute | inset_left(offset.x) | inset_top(offset.y) | border | border_lightrounded | pad_x(1),
    )


@component
def root() -> Div:
    rects = use_rects()

    return Div(
        style=full | border | border_heavy,
        children=(
            draggable("Drag me!", Position(2, 1), rects.padding),
            draggable("No, me!", Position(20, 4), rects.padding),
        ),
    )


# --8<-- [end:example]

DRAG = (
    MouseDown(absolute=Position(5, 3), button=1),
    MouseMoved(absolute=Position(7, 5), button=1),
    MouseMoved(absolute=Position(9, 7), button=1),
    MouseUp(absolute=Position(9, 7), button=1),
)

DRAG_PAST_THE_EDGE = (
    MouseDown(absolute=Position(22, 6), button=1),
    MouseMoved(absolute=Position(40, 9), button=1),
    MouseMoved(absolute=Position(60, 20), button=1),
    MouseUp(absolute=Position(60, 20), button=1),
)

SCREENSHOTS = [
    ScreenshotSpec(root(), "draggable", (40, 10)),
    ScreenshotSpec(root(), "draggable-dragged", (40, 10), events=DRAG),
    ScreenshotSpec(root(), "draggable-past-the-edge", (40, 10), events=DRAG_PAST_THE_EDGE),
]


if __name__ == "__main__":
    asyncio.run(app(root()))
