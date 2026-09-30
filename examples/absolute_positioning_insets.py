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
            Div(
                style=row | grow(1) | border_heavy | justify_children_center | align_children_center,
                children=[
                    Text(
                        style=position_absolute | inset_left(3) | inset_top(3),
                        content="position_absolute | inset_left(3) | inset_top(3)",
                    ),
                    Text(
                        style=inset_center_center | margin_left(-2) | margin_top(-4),
                        content="inset_center_center | margin_left(-2) | margin_top(-4)",
                    ),
                    Text(
                        style=inset_bottom_right | margin_bottom(4),
                        content="inset_bottom_right | margin_bottom(4)",
                    ),
                    Text(
                        style=inset_top_left,
                        content="inset_top_left",
                    ),
                    Text(
                        style=inset_top_center,
                        content="inset_top_center",
                    ),
                    Text(
                        style=inset_top_right,
                        content="inset_top_right",
                    ),
                    Text(
                        style=inset_center_left,
                        content="inset_center_left",
                    ),
                    Text(
                        style=inset_center_center,
                        content="inset_center_center",
                    ),
                    Text(
                        style=inset_center_right,
                        content="inset_center_right",
                    ),
                    Text(
                        style=inset_bottom_left,
                        content="inset_bottom_left",
                    ),
                    Text(
                        style=inset_bottom_center,
                        content="inset_bottom_center",
                    ),
                    Text(
                        style=inset_bottom_right,
                        content="inset_bottom_right",
                    ),
                ],
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
            dimensions=(60, 25),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "absolute-positioning-insets.svg", indent=1),
                Quit(),
            ],
        )
    )
