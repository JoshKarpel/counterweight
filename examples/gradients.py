import asyncio

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.styles import LinearGradient
from counterweight.styles.utilities import *

logger = get_logger()


@component
def root() -> Div:
    return Div(
        style=row
        | align_self_stretch
        | align_children_center
        | border_light
        | margin_5
        | Style(
            border=Border(
                style=CellStyle(
                    foreground=LinearGradient(
                        stops=(
                            Color.from_name("black"),
                            Color.from_name("red"),
                        ),
                        angle=45,
                    ),
                    background=LinearGradient(
                        stops=(
                            Color.from_name("teal"),
                            Color.from_name("yellow"),
                        ),
                        angle=45,
                    ),
                )
            ),
            margin=Margin(
                color=LinearGradient(
                    stops=(
                        Color.from_name("red"),
                        Color.from_name("cyan"),
                    ),
                    angle=0,
                )
            ),
            content=Content(
                color=LinearGradient(
                    stops=(
                        Color.from_name("orange"),
                        Color.from_name("blue"),
                    ),
                    angle=90,
                )
            ),
        ),
        children=[],
    )


if __name__ == "__main__":
    asyncio.run(app(root))
