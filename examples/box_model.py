# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div
from counterweight.styles.utilities import *


@component
def root() -> Div:
    return Div(
        style=col,
        children=[
            Div(
                style=grow(1)
                | content_color("green", 500)
                | padding_color("orange", 500)
                | pad_x(2)
                | pad_y(1)
                | border_lightrounded
                | border_bg("blue", 500)
                | margin_color("red", 500)
                | margin_x(2)
                | margin_y(1)
            )
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
            dimensions=(30, 10),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "box-model.svg", indent=1),
                Quit(),
            ],
        )
    )
