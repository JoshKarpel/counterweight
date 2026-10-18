import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.gradients import Hint
from counterweight.gradients import conic_gradient
from counterweight.gradients import linear_gradient
from counterweight.gradients import radial_gradient
from counterweight.painters.pixels import HalfBlockGradient
from counterweight.styles import CellStyle
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec


def labeled(label: str, box: Div | Canvas) -> Div:
    return Div(style=col | gap(0), children=(Text(content=label), box))


SWATCH = size(16, 5)

# --8<-- [start:linear]


@component
def linear() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            labeled("to right", Div(style=SWATCH | content_gradient(linear_gradient(rose_500, sky_500, to="right")))),
            labeled("angle=45", Div(style=SWATCH | content_gradient(linear_gradient(rose_500, sky_500, angle=45)))),
            labeled(
                "to top right",
                Div(style=SWATCH | content_gradient(linear_gradient(rose_500, sky_500, to="top right"))),
            ),
        ),
    )


# --8<-- [end:linear]

# --8<-- [start:shapes]


@component
def shapes() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            labeled("ellipse", Div(style=SWATCH | content_gradient(radial_gradient(amber_300, violet_900)))),
            labeled(
                "circle at a corner",
                Div(
                    style=SWATCH | content_gradient(radial_gradient(amber_300, violet_900, shape="circle", at=(0, 0))),
                ),
            ),
            labeled(
                "conic",
                Div(
                    style=SWATCH | content_gradient(conic_gradient(rose_500, amber_300, teal_500, violet_600, rose_500))
                ),
            ),
        ),
    )


# --8<-- [end:shapes]

# --8<-- [start:stops]


@component
def stops() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            labeled(
                "a hint at 0.2",
                Div(style=SWATCH | content_gradient(linear_gradient(gray_950, Hint(0.2), gray_100, to="right"))),
            ),
            labeled(
                "hard stops",
                Div(
                    style=SWATCH
                    | content_gradient(
                        linear_gradient(
                            (rose_500, 0, 1 / 3), (amber_300, 1 / 3, 2 / 3), (teal_500, 2 / 3, 1), to="right"
                        )
                    ),
                ),
            ),
            labeled(
                "repeating",
                Div(
                    style=SWATCH
                    | content_gradient(
                        linear_gradient((sky_500, 0), (gray_950, 0.2), (sky_500, 0.4), angle=120, repeating=True)
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:stops]

# --8<-- [start:interpolation]


@component
def interpolation() -> Div:
    return Div(
        style=col | gap(0),
        children=tuple(
            Div(
                style=row,
                children=(
                    Text(content=space, style=width(8)),
                    Div(
                        style=size(40, 1)
                        | content_gradient(linear_gradient(blue_600, yellow_300, to="right", interpolation=space)),
                    ),
                ),
            )
            for space in ("srgb", "oklab", "oklch")
        ),
    )


# --8<-- [end:interpolation]

# --8<-- [start:slots]

SUNRISE = linear_gradient(amber_300, rose_500, to="right")


@component
def slots() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            Div(
                style=size(20, 5) | border | border_heavy | border_gradient(SUNRISE),
                children=(Text(content="gradient border", style=pad_x(1)),),
            ),
            Div(
                style=size(24, 5) | pad_x(1),
                children=(
                    Text(
                        content=(
                            Chunk(content="Gradient text, "),
                            Chunk(content="with a highlight", style=CellStyle(bold=True)),
                            Chunk(content=" that continues it"),
                        ),
                        style=text_wrap_pretty | text_gradient(SUNRISE),
                    ),
                ),
            ),
            Div(
                style=size(20, 5)
                | pad(1)
                | padding_gradient(linear_gradient(teal_500, sky_700))
                | content_gradient(radial_gradient(gray_100, gray_400)),
            ),
        ),
    )


# --8<-- [end:slots]

# --8<-- [start:boxes]

DUSK = linear_gradient(violet_500, sky_400, to="right")
DUSK_OVER_THE_MARGIN = linear_gradient(violet_500, sky_400, to="right", box="margin")


@component
def boxes() -> Div:
    return Div(
        style=col,
        children=(
            Text(content="each over its own box"),
            Div(style=size(12, 2) | margin_x(4) | margin_gradient(DUSK) | content_gradient(DUSK)),
            Text(content="both over the margin box"),
            Div(
                style=size(12, 2)
                | margin_x(4)
                | margin_gradient(DUSK_OVER_THE_MARGIN)
                | content_gradient(DUSK_OVER_THE_MARGIN)
            ),
        ),
    )


# --8<-- [end:boxes]

# --8<-- [start:canvas]

ARC = conic_gradient(rose_500, amber_300, teal_500, violet_600, rose_500)


@component
def on_a_canvas() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            labeled("content_gradient", Div(style=SWATCH | content_gradient(ARC))),
            labeled("HalfBlockGradient", Canvas(painter=HalfBlockGradient(ARC), style=SWATCH)),
        ),
    )


# --8<-- [end:canvas]

SCREENSHOTS = [
    ScreenshotSpec(linear(), "gradients-linear", (56, 6)),
    ScreenshotSpec(shapes(), "gradients-shapes", (56, 6)),
    ScreenshotSpec(stops(), "gradients-stops", (56, 6)),
    ScreenshotSpec(interpolation(), "gradients-interpolation", (48, 3)),
    ScreenshotSpec(slots(), "gradients-slots", (68, 5)),
    ScreenshotSpec(boxes(), "gradients-boxes", (26, 6)),
    ScreenshotSpec(on_a_canvas(), "gradients-canvas", (36, 6)),
]

if __name__ == "__main__":
    roots = {root.__name__: root for root in (linear, shapes, stops, interpolation, slots, boxes, on_a_canvas)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else linear()))
