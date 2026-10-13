import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

container_style = fill(1) | align_self_stretch | border_collapse
box_style = fill(1) | align_self_stretch | center_children


def box(s: str) -> Div:
    return Div(
        style=box_style | border | border_double,
        children=(
            Text(
                style=text_justify_center | text_color("cyan", 500),
                content=s,
            ),
        ),
    )


@component
def root() -> Div:
    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        match event:
            case KeyPressed(key=Key.Space):
                return ToggleBorderHealing()
            case _:
                return None

    return Div(
        style=row | container_style,
        on_input=on_input,
        children=(
            Div(
                style=col | container_style,
                children=(box("A1"), box("A2")),
            ),
            Div(
                style=col | container_style,
                children=(
                    Div(style=row | container_style, children=(box("B1"), box("B2"))),
                    Div(style=row | container_style, children=(box("C1"), box("C2"), box("C3"), box("C4"))),
                    Div(style=row | container_style, children=(box("D1"), box("D2"), box("D3"))),
                ),
            ),
        ),
    )


# --8<-- [end:example]

# --8<-- [start:clipped]


@component
def clipped() -> Div:
    return Div(
        style=row | gap(2),
        children=tuple(
            Div(
                style=border | border_light | size(16, 5) | overflow,
                children=(
                    Div(
                        style=position_absolute | inset_top(-1) | inset_left(2) | size(11, 3) | border | border_light,
                        children=(Text(content=f" {name}"),),
                    ),
                ),
            )
            for name, overflow in (("visible", overflow_visible), ("hidden", overflow_hidden))
        ),
    )


# --8<-- [end:clipped]

# --8<-- [start:raised]


@component
def raised() -> Div:
    return Div(
        style=col,
        children=(
            Div(style=border | border_light | size(24, 3), children=(Text(content="A panel"),)),
            Text(
                content="A raised box",
                style=z(1) | position_absolute | inset_top(2) | inset_left(4) | border | border_light,
            ),
        ),
    )


# --8<-- [end:raised]

SCREENSHOTS = [
    ScreenshotSpec(root(), "border-healing-on", (60, 20)),
    ScreenshotSpec(root(), "border-healing-off", (60, 20), events=[KeyPressed(key=Key.Space)]),
    ScreenshotSpec(clipped(), "border-healing-clipped", (34, 5)),
    ScreenshotSpec(raised(), "border-healing-raised", (24, 5)),
    ScreenshotSpec(raised(), "border-healing-raised-off", (24, 5), events=[ToggleBorderHealing()]),
]


if __name__ == "__main__":
    asyncio.run(app(root()))
