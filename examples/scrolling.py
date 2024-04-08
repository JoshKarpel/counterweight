import asyncio
from itertools import cycle

from more_itertools import take
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *

logger = get_logger()

long_text = "\n".join(take(100, cycle(("foo", "bar", "baz"))))


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | border_heavy,
        children=[
            Div(
                style=row | align_self_stretch | border_heavy,
                children=[
                    Text(
                        style=border_lightrounded,
                        content=long_text,
                    ),
                    Text(
                        style=border_lightrounded,
                        content=long_text,
                    ),
                ],
            ),
            Div(
                style=row | align_self_stretch | border_heavy,
                children=[
                    Text(
                        style=border_lightrounded,
                        content=long_text,
                    ),
                    Text(
                        style=border_lightrounded,
                        content=long_text,
                    ),
                ],
            ),
        ],
    )


if __name__ == "__main__":
    asyncio.run(app(root))
