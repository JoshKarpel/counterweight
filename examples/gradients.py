import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.gradients import conic_gradient
from counterweight.gradients import linear_gradient
from counterweight.gradients import radial_gradient
from counterweight.hooks import use_clock
from counterweight.painters.pixels import HalfBlockGradient
from counterweight.styles.utilities import *

FRAME = timedelta(seconds=1 / 30)
DEGREES_PER_SECOND = 60


@component
def root() -> Div:
    angle = use_clock(FRAME).since_mount.total_seconds() * DEGREES_PER_SECOND

    return Div(
        style=col | full | gap(1) | pad(1) | content_color("gray", 950),
        children=(
            Text(
                content="Gradients, turning",
                style=text_gradient(linear_gradient(amber_300, rose_500, to="right")) | text_bg("gray", 950),
            ),
            Div(
                style=row | grow(1) | gap(2),
                children=(
                    Div(
                        style=grow(1)
                        | border
                        | border_heavy
                        | border_gradient(
                            conic_gradient(rose_500, amber_300, teal_400, violet_500, rose_500, start=angle)
                        )
                        | content_gradient(linear_gradient(sky_700, gray_950, violet_900, angle=angle)),
                    ),
                    Canvas(
                        painter=HalfBlockGradient(
                            conic_gradient(rose_500, amber_300, teal_400, violet_500, rose_500, start=-angle)
                        ),
                        style=grow(1),
                    ),
                    Div(
                        style=grow(1)
                        | content_gradient(
                            radial_gradient(
                                (amber_300, 0),
                                (rose_600, 0.15),
                                (gray_950, 0.3),
                                shape="circle",
                                at=(0.5 + 0.3 * ((angle % 360) / 180 - 1), 0.5),
                                repeating=True,
                            )
                        ),
                    ),
                ),
            ),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
