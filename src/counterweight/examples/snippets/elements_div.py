"""
Elements: Div

Cards that select on a click, which bubbles up from their text.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

# --8<-- [start:example]

CARD = col | border | border_lightrounded | border_color("slate", 500) | pad_x(1) | width(24)
SELECTED_CARD = border_heavy | border_color("sky", 400)


@component
def card(title: str, body: str) -> Div:
    is_selected, set_selected = use_state(False)

    def flip() -> None:
        set_selected(not is_selected)

    return Div(
        style=CARD | (SELECTED_CARD if is_selected else default),
        on_input=on_click(flip),
        children=(
            Text(style=text_color("sky", 300), content=title),
            Text(style=text_wrap_stable | text_color("slate", 300), content=body),
        ),
    )


@component
def root() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            card("Inbox", "Messages waiting for a reply."),
            card("Drafts", "Messages you started and haven't sent."),
            card("Archive", "Everything else."),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position

CLICK_DRAFTS_BODY = (MouseDown(absolute=Position(30, 2), button=1), MouseUp(absolute=Position(30, 2), button=1))
CLICK_ARCHIVE_BORDER = (MouseDown(absolute=Position(60, 0), button=1), MouseUp(absolute=Position(60, 0), button=1))

STILLS = [Still("elements-div-selected", root(), (76, 5), steps=CLICK_DRAFTS_BODY)]

DEMOS = [
    Demo(
        "elements-div",
        root(),
        (76, 5),
        steps=[
            *paced(
                [*CLICK_DRAFTS_BODY, *CLICK_ARCHIVE_BORDER, *CLICK_DRAFTS_BODY],
                pause=AdvanceClock(by=timedelta(milliseconds=500)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
