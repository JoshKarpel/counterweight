import asyncio
import sys
from dataclasses import dataclass

from codegen.generate_logo import icons
from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import Receiver
from counterweight.geometry import Position
from counterweight.hooks import use_state
from counterweight.painters.pixels import Fit
from counterweight.painters.pixels import HalfBlocks
from counterweight.painters.pixels import Pixels
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:pixels]

SKY_TOP = Color.from_hex("#1e1b4b")
SKY_BOTTOM = Color.from_hex("#f97316")
SUN = Color.from_hex("#fde047")
SEA = Color.from_hex("#0e7490")


def blend(a: Color, b: Color, t: float) -> Color:
    return Color(*(round(x + (y - x) * t) for x, y in zip(a, b, strict=True)))


def sunset(width: int, height: int) -> Pixels:
    """A sky that brightens toward the horizon, a sun setting on it, and the sea below."""
    horizon = height * 3 // 4
    radius = width / 4

    def color(x: int, y: int) -> Color:
        if y >= horizon:
            return SEA
        if (x + 0.5 - width / 2) ** 2 + (y + 0.5 - horizon) ** 2 < radius**2:
            return SUN
        return blend(SKY_TOP, SKY_BOTTOM, y / horizon)

    rgba = b"".join(bytes((*color(x, y), 255)) for y in range(height) for x in range(width))
    return Pixels(width, height, rgba)


SUNSET = sunset(16, 16)


@component
def picture() -> Canvas:
    return Canvas(painter=HalfBlocks(SUNSET), style=border)


# --8<-- [end:pixels]

# --8<-- [start:sizing]


def labeled(label: str, canvas: Canvas) -> Div:
    return Div(style=col | align_children_start, children=(Text(content=label), canvas))


@component
def sizing() -> Div:
    return Div(
        style=row | gap(2) | align_children_start,
        children=(
            labeled("natural size", Canvas(painter=HalfBlocks(SUNSET), style=border)),
            labeled("width(10)", Canvas(painter=HalfBlocks(SUNSET), style=border | width(10))),
            labeled("height(4)", Canvas(painter=HalfBlocks(SUNSET), style=border | height(4))),
            Div(
                style=col | width(12),
                children=(
                    Text(content="min_width(0)"),
                    Div(
                        style=row,
                        children=(Canvas(painter=HalfBlocks(SUNSET), style=border | min_width(0)),),
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:sizing]

# --8<-- [start:fit]

FITS: tuple[Fit, ...] = ("fill", "contain", "cover", "none", "scale-down")


@component
def fits() -> Div:
    return Div(
        style=row | gap(1),
        children=tuple(
            labeled(f'fit="{fit}"', Canvas(painter=HalfBlocks(SUNSET, fit=fit), style=border | size(22, 6)))
            for fit in FITS
        ),
    )


# --8<-- [end:fit]

# --8<-- [start:image]

# Convert the image once, before the app starts, rather than in a render.
LOGO = Pixels.from_image(icons()["favicon.png"])


@component
def image() -> Div:
    return Div(
        style=row | gap(2) | align_children_start,
        children=(
            Canvas(painter=HalfBlocks(LOGO), style=border | content_color("slate", 700)),
            Canvas(painter=HalfBlocks(LOGO, fit="contain"), style=border | size(24, 6) | content_color("slate", 700)),
        ),
    )


# --8<-- [end:image]

# --8<-- [start:painter]


@dataclass(frozen=True, slots=True)
class Ruler:
    """Draws a ruler as wide as whatever box it's given: a tick on every column, and a label on every tenth."""

    natural_size: tuple[int, int] = (0, 2)
    keeps_aspect_ratio: bool = False

    def draw(self, width: int, height: int) -> Rows:
        ticks = tuple(StyledGrapheme(grapheme="┴" if x % 10 == 0 else "╵" if x % 5 == 0 else "·") for x in range(width))
        labels = "".join(f"{x:<10}" for x in range(0, width, 10))[:width]
        label_style = CellStyle(foreground=Color.from_hex("#fbbf24"))
        return ticks, tuple(StyledGrapheme(grapheme=c, style=label_style) for c in labels)


@component
def ruler() -> Div:
    return Div(style=col, children=(Canvas(painter=Ruler(), style=border),))


# --8<-- [end:painter]

# --8<-- [start:paint]

BLANK = Pixels.blank(24, 16, Color.from_name("black"))
INK = Color.from_hex("#fbbf24")


@component
def paint() -> Div:
    pixels, set_pixels = use_state(BLANK)
    painter = HalfBlocks(pixels)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=a, button=1) | MouseMoved(absolute=a, button=1):
                content = receiver.rects.content
                under = painter.pixels_at(receiver.relative(a), content.width, content.height)
                set_pixels(lambda p: p.with_points(dict.fromkeys(under, INK)))
                return ()
            case _:
                return None

    return Div(style=col | align_children_start, children=(Canvas(painter=painter, style=border, on_input=on_input),))


# --8<-- [end:paint]


def stroke() -> tuple[MouseDown | MouseMoved, ...]:
    """A drag down and to the right across the canvas, which starts one cell inside its border."""
    start, *rest = (Position(2 + x, 2 + x // 3) for x in range(18))
    return (MouseDown(absolute=start, button=1), *(MouseMoved(absolute=p, button=1) for p in rest))


SCREENSHOTS = [
    ScreenshotSpec(picture(), "canvas-pixels", (20, 10)),
    ScreenshotSpec(sizing(), "canvas-sizing", (66, 11)),
    ScreenshotSpec(fits(), "canvas-fit", (118, 7)),
    ScreenshotSpec(image(), "canvas-image", (62, 18)),
    ScreenshotSpec(ruler(), "canvas-painter", (64, 4)),
    ScreenshotSpec(paint(), "canvas-paint", (28, 10), events=stroke()),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (picture, sizing, fits, image, ruler, paint)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else picture()))
