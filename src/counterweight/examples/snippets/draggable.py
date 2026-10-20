"""
Cookbook: Draggable components

Boxes dragged around with the mouse.
"""

import asyncio
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import component
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
from counterweight.hooks import use_rects
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from counterweight.utils import clamp

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


ROOTS = (root,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

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

STILLS = [
    Still("draggable", root(), (40, 10)),
    Still("draggable-dragged", root(), (40, 10), steps=DRAG),
    Still("draggable-past-the-edge", root(), (40, 10), steps=DRAG_PAST_THE_EDGE),
]


def drag(start: Position, end: Position, moves: int) -> list[MouseDown | MouseMoved | MouseUp]:
    """A drag from `start` to `end` in `moves` even steps, as a hand moves the mouse."""
    path = [
        Position(start.x + (end.x - start.x) * step // moves, start.y + (end.y - start.y) * step // moves)
        for step in range(1, moves + 1)
    ]
    return [
        MouseDown(absolute=start, button=1),
        *(MouseMoved(absolute=position, button=1) for position in path),
        MouseUp(absolute=end, button=1),
    ]


DEMOS = [
    Demo(
        "draggable",
        root(),
        (40, 10),
        steps=[
            *paced(
                [*drag(Position(5, 3), Position(9, 7), moves=8), *drag(Position(24, 6), Position(44, 14), moves=12)],
                pause=AdvanceClock(by=timedelta(milliseconds=60)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
