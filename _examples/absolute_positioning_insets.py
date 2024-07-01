# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *


@component
def root() -> Div:
    return Div(
        style=col | align_self_stretch,
        children=[
            Div(
                style=row | align_self_stretch | border_heavy,
                children=[
                    Text(
                        style=inset_top_left,
                        content="inset_top_left",
                    ),
                    Text(
                        style=inset_top_left | absolute(x=3, y=3),
                        content="inset_top_left | absolute(x=3, y=3)",
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
                        style=inset_center_center | absolute(x=-2, y=-4),
                        content="inset_center_center | absolute(x=-2, y=-4)",
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
                    Text(
                        style=inset_bottom_right | absolute(y=-4),
                        content="inset_bottom_right | absolute(y=-4)",
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
                Screenshot.to_file(THIS_DIR / "absolute-positioning-insets.svg", indent=1),
                Quit(),
            ],
        )
    )
