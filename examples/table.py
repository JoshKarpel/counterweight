import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import Div, Text, component
from counterweight.styles.utilities import *

logger = get_logger()

style = align_self_stretch | justify_children_center | align_children_center


@component
def root() -> Div:
    return Div(
        style=row | style,
        children=[
            Div(
                style=col | style,
                children=[box("A1"), box("A2")],
            ),
            Div(
                style=col | style,
                children=[
                    Div(style=row | style, children=[box("B1"), box("B2")]),
                    Div(style=row | style, children=[box("C1"), box("C2"), box("C3"), box("C4")]),
                    Div(style=row | style, children=[box("D1"), box("D2"), box("D3")]),
                ],
            ),
        ],
    )


@component
def box(s: str) -> Div:
    return Div(
        style=style | border_light,
        children=[Text(style=text_justify_center, content=s)],
    )


asyncio.run(app(root))
