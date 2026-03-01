# --8<-- [start:example]
import waxy

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles import Style
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
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute, inset_top=waxy.Length(-1), inset_left=waxy.Length(1)
                            )
                        ),
                        content=" Top-Left Title ",
                    ),
                    Text(
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute,
                                inset_top=waxy.Length(-1),
                                inset_left=waxy.Auto(),
                                inset_right=waxy.Auto(),
                            )
                        ),
                        content=" Top-Center Title ",
                    ),
                    Text(
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute, inset_top=waxy.Length(-1), inset_right=waxy.Length(1)
                            )
                        ),
                        content=" Top-Right Title ",
                    ),
                    Text(
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute, inset_bottom=waxy.Length(-1), inset_left=waxy.Length(1)
                            )
                        ),
                        content=" Bottom-Left Title ",
                    ),
                    Text(
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute,
                                inset_bottom=waxy.Length(-1),
                                inset_left=waxy.Auto(),
                                inset_right=waxy.Auto(),
                            )
                        ),
                        content=" Bottom-Center Title ",
                    ),
                    Text(
                        style=Style(
                            layout=waxy.Style(
                                position=waxy.Position.Absolute,
                                inset_bottom=waxy.Length(-1),
                                inset_right=waxy.Length(1),
                            )
                        ),
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
