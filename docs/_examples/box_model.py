# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div
from counterweight.styles.utilities import *


@component
def root() -> Div:
    return Div(
        style=content_green_500
        | padding_pink_500
        | pad_x_2
        | pad_y_1
        | border_lightrounded
        | border_bg_red_500
        | margin_blue_500
        | margin_x_2
        | margin_y_1
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
            dimensions=(30, 12),
            autopilot=[
                Screenshot.to_file(THIS_DIR / "box-model.svg", indent=1),
                Quit(),
            ],
        )
    )
