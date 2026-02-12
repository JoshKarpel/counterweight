# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *

extra_style = border_light | pad_1 | margin_1


@component
def root() -> Div:
    return Div(
        style=col | justify_children_space_around,
        children=[
            Div(
                style=border_heavy,
                children=[
                    Text(
                        style=text_green_600,
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    )
                ]
                + [
                    Text(
                        style=absolute(x=x, y=y) | extra_style | margin_red_600,
                        content=f"absolute(x={x}, y={y})",
                    )
                    for x, y in (
                        (0, 0),
                        (10, -7),
                        (33, 3),
                    )
                ],
            ),
            Div(
                style=border_heavy,
                children=[
                    Text(
                        style=text_cyan_600,
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    )
                ]
                + [
                    Text(
                        style=absolute(x=x, y=y) | extra_style | margin_amber_600,
                        content=f"absolute(x={x}, y={y})",
                    )
                    for x, y in (
                        (0, 0),
                        (10, -7),
                        (33, 3),
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
            dimensions=(60, 30),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "absolute-positioning.svg", indent=1),
                Quit(),
            ],
        )
    )
