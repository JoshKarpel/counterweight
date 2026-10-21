"""
Elements: Canvas

Pictures drawn in half blocks: sized, fitted to their box, converted from Pillow, drawn by a painter of your own, and painted with the mouse,
and pictures of the screen: a screenshot of a panel, and a wipe from one panel's picture to another's.
"""

import asyncio
import sys
from dataclasses import dataclass
from datetime import timedelta
from functools import cache

from PIL import Image
from PIL import ImageOps

from counterweight import app
from counterweight.animation import ease_in_out
from counterweight.components import component
from counterweight.controls import Screenshot
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.hooks import use_progress
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.paint import Cell
from counterweight.paint import Frame
from counterweight.paint import rows_of
from counterweight.painters import Fit
from counterweight.painters import HalfBlocks
from counterweight.painters import PaintView
from counterweight.painters import Pixels
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles.utilities import *

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


@cache
def mandelbrot() -> Pixels:
    """Pillow's Mandelbrot set, colored, converted the first time it's drawn rather than in every render."""
    gray = Image.effect_mandelbrot((40, 32), (-2.2, -1.2, 0.8, 1.2), 100)
    return Pixels.from_image(ImageOps.colorize(gray, black="#1e1b4b", white="#fde047", mid="#f97316"))


@component
def image() -> Div:
    pixels = mandelbrot()
    return Div(
        style=row | gap(2) | align_children_start,
        children=(
            Canvas(painter=HalfBlocks(pixels), style=border | content_color("slate", 700)),
            Canvas(painter=HalfBlocks(pixels, fit="contain"), style=border | size(24, 6) | content_color("slate", 700)),
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

# --8<-- [start:screenshot]


@component
def snapshot() -> Div:
    count, set_count = use_state(0)
    panel = use_state(ElementHandle)[0]
    where = use_rects(panel).border
    no_picture: PaintView | None = None
    taken, set_taken = use_state(no_picture)

    def keep(frame: Frame) -> None:
        # Built once, from the frame as it was, rather than in every render.
        set_taken(frame.paint.as_painter(where))

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="+"):
                set_count(lambda count: count + 1)
                return ()
            case KeyPressed(key="s"):
                return (Screenshot(handler=keep),)
            case _:
                return None

    return Div(
        style=row | gap(2),
        on_input=on_input,
        children=(
            Div(
                handle=panel,
                style=border | border_lightrounded | border_color("teal", 400) | pad_x(1),
                children=(Text(content=f"Count: {count}"),),
            ),
            Text(content="Press s", style=text_color("slate", 400)) if taken is None else Canvas(painter=taken),
        ),
    )


# --8<-- [end:screenshot]

# --8<-- [start:transition]

type Picture = tuple[tuple[Cell, ...], ...]

NO_PICTURE: Picture = ()


def wipe(before: Picture, after: Picture, progress: float) -> Picture:
    """`after` from the left edge up to `progress` of the way across, and `before` from there on."""
    cut = round(ease_in_out(progress) * max((len(row) for row in before), default=0))
    return tuple((*new[:cut], *old[cut:]) for old, new in zip(before, after, strict=True))


def card(handle: ElementHandle, color: Color, lines: tuple[str, ...]) -> Div:
    return Div(
        handle=handle,
        style=col | border | border_lightrounded | border_color(color) | pad_x(1) | size(14, 5),
        children=tuple(Text(content=line, style=text_color(color)) for line in lines),
    )


@component
def transition() -> Div:
    first, second = use_state(ElementHandle)[0], use_state(ElementHandle)[0]
    before, after = use_rects(first).border, use_rects(second).border
    pictures, set_pictures = use_state((NO_PICTURE, NO_PICTURE))
    plays, set_plays = use_state(0)
    progress = use_progress(timedelta(seconds=1), deps=(plays,))

    def keep(frame: Frame) -> None:
        # The cells of each card, as they are in this frame, to mix on every frame of the wipe.
        set_pictures((frame.paint.cells_in(before), frame.paint.cells_in(after)))
        set_plays(lambda plays: plays + 1)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="s"):
                return (Screenshot(handler=keep),)
            case KeyPressed(key=Key.Space):
                set_plays(lambda plays: plays + 1)
                return ()
            case _:
                return None

    old, new = pictures
    return Div(
        style=row | gap(2),
        on_input=on_input,
        children=(
            card(first, Color.from_hex("#2dd4bf"), ("Before", "日本語", "─" * 10)),
            card(second, Color.from_hex("#fb7185"), ("After", "ひらがな", "═" * 10)),
            Text(content="Press s", style=text_color("slate", 400))
            if old == NO_PICTURE
            else Canvas(painter=PaintView(rows=rows_of(wipe(old, new, progress)), width=before.width)),
        ),
    )


# --8<-- [end:transition]


ROOTS = (picture, sizing, fits, image, ruler, paint, snapshot, transition)

# --8<-- [start:scenes]

from counterweight.autopilot import advance
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def stroke() -> tuple[MouseDown | MouseMoved, ...]:
    """A drag down and to the right across the canvas, which starts one cell inside its border."""
    start, *rest = (Position(2 + x, 2 + x // 3) for x in range(18))
    return (MouseDown(absolute=start, button=1), *(MouseMoved(absolute=p, button=1) for p in rest))


STILLS = [
    Still("canvas-pixels", picture(), (20, 10)),
    Still("canvas-sizing", sizing(), (66, 11)),
    Still("canvas-fit", fits(), (118, 7)),
    Still("canvas-image", image(), (70, 18)),
    Still("canvas-painter", ruler(), (64, 4)),
    Still("canvas-paint", paint(), (28, 10), steps=stroke()),
    Still("canvas-screenshot", snapshot(), (36, 3), steps=[*typed("++s"), *typed("++")]),
    Still("canvas-transition", transition(), (46, 5), steps=[*typed("s"), AdvanceClock(by=timedelta(seconds=0.5))]),
]

DEMOS = [
    Demo(
        "canvas-transition",
        transition(),
        (46, 5),
        steps=[
            AdvanceClock(by=timedelta(seconds=1)),
            *typed("s"),
            *advance(timedelta(seconds=2)),
            KeyPressed(key=Key.Space),
            *advance(timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
