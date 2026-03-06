# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *

extra_style = border_light | pad_x(1) | margin_x_1


@component
def root() -> Div:
    return Div(
        style=col | justify_children_space_around,
        children=[
            Div(
                style=grow(1) | border_heavy,
                children=[
                    Text(
                        style=text("green", 600),
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    )
                ]
                + [
                    Text(
                        style=position_absolute | inset_left(x) | inset_top(y) | extra_style | margin_color("red", 600),
                        content=f"inset_left({x}) | inset_top({y})",
                    )
                    for x, y in (
                        (0, 0),
                        (10, 5),
                        (20, 9),
                    )
                ],
            ),
            Div(
                style=grow(1) | border_heavy,
                children=[
                    Text(
                        style=text("cyan", 600),
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    )
                ]
                + [
                    Text(
                        style=position_absolute
                        | inset_left(x)
                        | inset_top(y)
                        | extra_style
                        | margin_color("amber", 600),
                        content=f"inset_left({x}) | inset_top({y})",
                    )
                    for x, y in (
                        (0, 0),
                        (10, 5),
                        (20, 9),
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
