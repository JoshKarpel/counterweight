# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *

extra_style = border_heavy | pad_1 | margin_1 | margin_red_600


@component
def root() -> Div:
    return Div(
        style=row,
        children=[
            Text(
                style=absolute(x=x, y=y) | extra_style,
                content=f"absolute(x={x}, y={y})",
            )
            for x, y in (
                (0, 0),
                (10, 10),
                (30, 20),
                (15, 25),
                (33, 3),
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
            dimensions=(60, 30),
            autopilot=[
                Screenshot.to_file(THIS_DIR / "absolute-positioning.svg", indent=1),
                Quit(),
            ],
        )
    )
