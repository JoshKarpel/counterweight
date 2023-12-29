import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()


# TODO: what happens if you tweak these (removing align_self_stretch definitely breaks it)
style = align_self_stretch | justify_children_center | align_children_center
bs = border_double


@component
def root() -> Div:
    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Space:
                return ToggleBorderHealing()
            case _:
                return None

    return Div(
        style=row | style,
        on_key=on_key,
        children=[
            Div(
                style=col | style,
                children=[
                    box("A1", edge_style=None),
                    box("A2", edge_style=border_bottom_left_right),
                ],
            ),
            Div(
                style=col | style,
                children=[
                    Div(
                        style=row | style,
                        children=[
                            box("B1", edge_style=border_top_bottom_right),
                            box("B2", edge_style=border_top_bottom_right),
                        ],
                    ),
                    Div(
                        style=row | style,
                        children=[
                            box("C1"),
                            box("C2"),
                            box("C3"),
                            box("C4"),
                        ],
                    ),
                    Div(
                        style=row | style,
                        children=[
                            box("D1"),
                            box("D2"),
                            box("D3"),
                        ],
                    ),
                ],
            ),
        ],
    )


@component
def box(s: str, edge_style: Style | None = border_bottom_right) -> Div:
    return Div(
        style=style | bs | edge_style,
        children=[Text(style=text_justify_center, content=s)],
    )


if __name__ == "__main__":
    asyncio.run(app(root))
