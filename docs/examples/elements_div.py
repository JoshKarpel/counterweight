import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.geometry import Position
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]

CARD = col | border | border_lightrounded | border_color("slate", 500) | pad_x(1) | width(24)
SELECTED_CARD = border_heavy | border_color("sky", 400)


@component
def card(title: str, body: str) -> Div:
    is_selected, set_selected = use_state(False)

    return Div(
        style=CARD | (SELECTED_CARD if is_selected else default),
        on_input=on_click(lambda: set_selected(not is_selected)),
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

CLICK_DRAFTS_BODY = (MouseDown(absolute=Position(30, 2), button=1), MouseUp(absolute=Position(30, 2), button=1))
CLICK_ARCHIVE_BORDER = (MouseDown(absolute=Position(60, 0), button=1), MouseUp(absolute=Position(60, 0), button=1))

SCREENSHOTS = [ScreenshotSpec(root(), "elements-div-selected", (76, 5), events=CLICK_DRAFTS_BODY)]

CASTS = [
    CastSpec(
        root(),
        "elements-div",
        (76, 5),
        steps=paced([*CLICK_DRAFTS_BODY, *CLICK_ARCHIVE_BORDER, *CLICK_DRAFTS_BODY], every=timedelta(milliseconds=500)),
    )
]


if __name__ == "__main__":
    asyncio.run(app(root()))
