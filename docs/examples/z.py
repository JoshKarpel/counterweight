# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *


@component
def root() -> Div:
    return Div(
        style=col,
        children=[
            Text(
                style=z(1)
                | position_absolute
                | inset_left(6)
                | inset_top(6)
                | border_lightrounded
                | margin(1)
                | margin_color("purple", 600),
                content="z = +1",
            ),
            Text(
                style=z(0)
                | position_absolute
                | inset_left(4)
                | inset_top(3)
                | border_lightrounded
                | margin(1)
                | margin_color("teal", 600),
                content="z =  0",
            ),
            Text(
                style=z(-1)
                | position_absolute
                | inset_left(0)
                | inset_top(0)
                | border_lightrounded
                | margin(1)
                | margin_color("red", 600),
                content="z = -1",
            ),
            Text(
                style=z(2)
                | position_absolute
                | inset_left(13)
                | inset_top(3)
                | border_lightrounded
                | margin(1)
                | margin_color("amber", 600),
                content="z = +2",
            ),
        ],
    )


# --8<-- [end:example]

if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    THIS_DIR = Path(__file__).parent

    asyncio.run(
        app(
            root,
            headless=True,
            dimensions=(30, 15),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "z.svg", indent=1),
                Quit(),
            ],
        )
    )
