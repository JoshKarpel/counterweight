# --8<-- [start:example]
import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.styles.styles import Style, TextWrap
from counterweight.styles.utilities import *

SAMPLE = "It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness."

WRAP_STYLE: dict[TextWrap, Style] = {
    "none": text_wrap_none,
    "stable": text_wrap_stable,
    "pretty": text_wrap_pretty,
    "balance": text_wrap_balance,
}


@component
def wrap_pane(mode: TextWrap) -> Div:
    return Div(
        style=grow(1) | min_width(0) | col | align_children_stretch | border_light | pad_x(1),
        children=[
            Text(
                content=f" {mode} ",
                style=position_absolute | inset_top(-1) | inset_left(1),
            ),
            Text(
                content=SAMPLE,
                style=grow(1) | WRAP_STYLE[mode],
            ),
        ],
    )


@component
def root() -> Div:
    return Div(
        style=col | full | align_children_stretch,
        children=[
            Div(
                style=row | grow(1) | align_children_stretch,
                children=[wrap_pane(mode) for mode in WRAP_STYLE],
            ),
        ],
    )


# --8<-- [end:example]

if __name__ == "__main__":
    from pathlib import Path

    THIS_DIR = Path(__file__).parent

    asyncio.run(
        app(
            root,
            headless=True,
            dimensions=(120, 14),
            autopilot=[
                Screenshot.to_file(THIS_DIR.parent / "assets" / "text-wrap.svg", indent=1),
                Quit(),
            ],
        )
    )
