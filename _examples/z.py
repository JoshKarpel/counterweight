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
                style=z(1) | absolute(6, 6) | border_lightrounded | margin_1 | margin_purple_600,
                content="z = +1",
            ),
            Text(
                style=z(0) | absolute(4, 3) | border_lightrounded | margin_1 | margin_teal_600,
                content="z =  0",
            ),
            Text(
                style=z(-1) | absolute(0, 0) | border_lightrounded | margin_1 | margin_red_600,
                content="z = -1",
            ),
            Text(
                style=z(2) | absolute(13, 3) | border_lightrounded | margin_1 | margin_amber_600,
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
                Screenshot.to_file(THIS_DIR / "z.svg", indent=1),
                Quit(),
            ],
        )
    )
