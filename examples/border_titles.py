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
                style=row | align_self_stretch | justify_children_center | align_children_center | border_lightrounded,
                children=[
                    Text(
                        style=inset_top_left | absolute(x=1, y=-1),
                        content=" Top-Left Title ",
                    ),
                    Text(
                        style=inset_top_center | absolute(x=0, y=-1),
                        content=" Top-Center Title ",
                    ),
                    Text(
                        style=inset_top_right | absolute(x=-1, y=-1),
                        content=" Top-Right Title ",
                    ),
                    Text(
                        style=inset_bottom_left | absolute(x=1, y=1),
                        content=" Bottom-Left Title ",
                    ),
                    Text(
                        style=inset_bottom_center | absolute(x=0, y=1),
                        content=" Bottom-Center Title ",
                    ),
                    Text(
                        style=inset_bottom_right | absolute(x=-1, y=1),
                        content=" Bottom-Right Title ",
                    ),
                    Text(
                        style=weight_none,
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
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
            dimensions=(70, 5),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "border-titles.svg", indent=1),
                Quit(),
            ],
        )
    )
