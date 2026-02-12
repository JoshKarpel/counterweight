# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *

extra_style = pad_1 | margin_1


@component
def root() -> Div:
    return Div(
        style=col | justify_children_space_between,
        children=[
            Div(
                style=row,
                children=[
                    Text(
                        style=relative(x=x, y=y) | extra_style | border_lightrounded | margin_red_600,
                        content=f"relative(x={x}, y={y})",
                    )
                    for x, y in (
                        (0, 0),
                        (0, 5),
                        (0, -3),
                    )
                ],
            ),
            Div(
                style=row,
                children=[
                    Text(
                        style=relative(x=x, y=y) | extra_style | border_heavy | margin_amber_600,
                        content=f"relative(x={x}, y={y})",
                    )
                    for x, y in (
                        (0, 0),
                        (3, 3),
                        (0, 0),
                    )
                ],
            ),
            Div(
                style=row,
                children=[
                    Text(
                        style=relative(x=x, y=y) | extra_style | border_light | margin_violet_700,
                        content=f"relative(x={x}, y={y})",
                    )
                    for x, y in (
                        (0, 0),
                        (5, 0),
                        (0, -5),
                    )
                ],
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
            dimensions=(80, 30),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "relative-positioning.svg", indent=1),
                Quit(),
            ],
        )
    )
