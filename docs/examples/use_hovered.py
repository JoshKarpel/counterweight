import asyncio
import sys
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import Wait
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import MouseMoved
from counterweight.geometry import Position
from counterweight.hooks import use_hovered
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:menu]


@component
def menu_item(label: str) -> Text:
    hovered = use_hovered()

    return Text(
        content=f"{'>' if hovered.border else ' '} {label}",
        style=pad_right(1) | (text_bg("sky", 800) if hovered.border else text_color("slate", 300)),
    )


@component
def menu() -> Div:
    return Div(
        style=col | border | border_lightrounded | fit_content_width,
        children=tuple(menu_item(label) for label in ("New file", "Open...", "Save", "Save as...", "Quit")),
    )


# --8<-- [end:menu]

# --8<-- [start:boxes]


@component
def boxes() -> Div:
    hovered = use_hovered()

    return Div(
        style=col
        | margin(1)
        | margin_color("slate", 800)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if hovered.border else None)
        | pad(1)
        | padding_color("slate", 700)
        | content_color("slate", 900)
        | fit_content_width,
        children=tuple(
            Text(
                content=f"{name:<7} {'yes' if is_hovered else 'no'}",
                style=text_color("emerald" if is_hovered else "slate", 400),
            )
            for name, is_hovered in (
                ("content", hovered.content),
                ("padding", hovered.padding),
                ("border", hovered.border),
                ("margin", hovered.margin),
            )
        ),
    )


# --8<-- [end:boxes]

# use_hovered reads use_mouse, which subscribes in an effect, and effects only start while the app waits for something,
# which an autopilot that hands it a step every frame never does; a moment's wait lets it subscribe.
SUBSCRIBE = Wait(timedelta(milliseconds=1))


def moves(*positions: tuple[int, int]) -> list[MouseMoved]:
    return [MouseMoved(absolute=Position(x, y), button=None) for x, y in positions]


SCREENSHOTS = [
    ScreenshotSpec(menu(), "use-hovered-menu", (24, 7), events=[SUBSCRIBE, *moves((20, 1), (6, 3))]),
    ScreenshotSpec(boxes(), "use-hovered-boxes", (24, 10), events=[SUBSCRIBE, *moves((2, 3))]),
]

CASTS = [
    CastSpec(
        menu(),
        "use-hovered-menu",
        (24, 7),
        steps=[
            SUBSCRIBE,
            *paced(
                moves((20, 0), (14, 1), (8, 2), (7, 3), (6, 4), (6, 5), (12, 6), (20, 6)),
                every=timedelta(milliseconds=300),
            ),
        ],
    ),
    CastSpec(
        boxes(),
        "use-hovered-boxes",
        (24, 10),
        steps=[
            SUBSCRIBE,
            *paced(
                moves((20, 4), (16, 4), (15, 4), (14, 4), (10, 4), (10, 7), (10, 8), (10, 9), (20, 9)),
                every=timedelta(milliseconds=400),
            ),
        ],
    ),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (menu, boxes)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else menu()))
