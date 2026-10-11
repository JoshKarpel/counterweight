from counterweight.components import component
from counterweight.controls import AnyControl, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

container_style = fill(1) | align_self_stretch | border_collapse
box_style = fill(1) | align_self_stretch | center_children


def box(s: str) -> Div:
    return Div(
        style=box_style | border | border_double,
        children=[
            Text(
                style=text_justify_center | text_color("cyan", 500),
                content=s,
            )
        ],
    )


@component
def root() -> Div:
    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Space:
                return ToggleBorderHealing()
            case _:
                return None

    return Div(
        style=row | container_style,
        on_key=on_key,
        children=[
            Div(
                style=col | container_style,
                children=[box("A1"), box("A2")],
            ),
            Div(
                style=col | container_style,
                children=[
                    Div(style=row | container_style, children=[box("B1"), box("B2")]),
                    Div(style=row | container_style, children=[box("C1"), box("C2"), box("C3"), box("C4")]),
                    Div(style=row | container_style, children=[box("D1"), box("D2"), box("D3")]),
                ],
            ),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [
    ScreenshotSpec(root, "border-healing-on", (60, 20)),
    ScreenshotSpec(root, "border-healing-off", (60, 20), events=[KeyPressed(key=Key.Space)]),
]
