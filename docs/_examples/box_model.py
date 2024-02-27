# --8<-- [start:example]
from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Text
from counterweight.styles.utilities import *


@component
def root() -> Text:
    return Text(
        style=text_bg_amber_500
        | padding_green_500
        | pad_2
        | border_bg_red_500
        | border_light
        | margin_blue_500
        | margin_2,
        content="Hello, World!",
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
                Screenshot.to_file(THIS_DIR / "box-model.svg", indent=1),
                Quit(),
            ],
        )
    )
