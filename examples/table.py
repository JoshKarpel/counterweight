import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import Div, Text, component
from counterweight.styles.utilities import *

logger = get_logger()

ROWS = (
    ("foo", "bar", "baz"),
    ("foo", "bar", "baz"),
    ("foo", "bar", "baz"),
)


@component
def root() -> Div:
    return Div(
        style=row | align_self_stretch | align_children_center,
        children=[table()],
    )


@component
def table() -> Div:
    rows = [Div(children=[Text(content=entry) for entry in row]) for row in ROWS]

    return Div(
        style=col | justify_children_center | align_children_center,
        children=rows,
    )


asyncio.run(app(root))
