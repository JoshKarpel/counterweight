"""
Pictures made of pixels, and the painters that draw them in cells.

`Pixels` is the picture, which knows nothing about cells, and `HalfBlocks` draws one in a canvas's cells.
`HalfBlockGradient` draws a gradient that way, at whatever size its canvas is.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from math import ceil
from typing import Literal
from typing import Protocol
from typing import assert_never

from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.geometry import Region
from counterweight.gradients import Gradient
from counterweight.gradients import field_indices
from counterweight.gradients import ramp
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Color


class SupportsRGBA(Protocol):
    """An image that converts to RGBA bytes, as a [Pillow](https://pillow.readthedocs.io/) `Image` does."""

    @property
    def size(self) -> tuple[int, int]:
        """The image's width and height, in pixels."""

    def convert(self, mode: str) -> SupportsRGBA:
        """The image in another mode, such as `"RGBA"`."""

    def tobytes(self) -> bytes:
        """The image's pixels, row by row."""


@dataclass(frozen=True, slots=True)
class Pixels:
    """
    A picture: a `width` by `height` grid of pixels, as RGBA bytes, row by row from the top left,
    four bytes (red, green, blue and alpha) to a pixel.
    It raises `ValueError` if the bytes aren't four for each pixel.

    Two `Pixels` are equal when their bytes are, which a canvas compares its painter by from frame to frame,
    so changing a picture means making a new one, as `with_points` does.
    Build or decode one outside of rendering, such as when the app starts or in an effect that sets state,
    since it costs as much as the picture has pixels.
    """

    width: int
    height: int
    rgba: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"A picture can't be {self.width}x{self.height} pixels")
        if len(self.rgba) != self.width * self.height * 4:
            raise ValueError(
                f"A {self.width}x{self.height} picture has {self.width * self.height * 4} bytes of RGBA, "
                f"not {len(self.rgba)}"
            )

    @classmethod
    def blank(cls, width: int, height: int, color: Color) -> Pixels:
        """A `width` by `height` picture of pixels all `color`."""
        return cls(width, height, _opaque(color) * (width * height))

    @classmethod
    def from_points(cls, width: int, height: int, points: Mapping[Position, Color], default: Color) -> Pixels:
        """A `width` by `height` picture of `default` pixels, but for the `points` given their own colors."""
        return cls.blank(width, height, default).with_points(points)

    @classmethod
    def from_gradient(cls, width: int, height: int, gradient: Gradient) -> Pixels:
        """
        A `width` by `height` picture of `gradient`, mapped over the whole picture, with its pixels taken as square,
        as [`HalfBlocks`][counterweight.painters.HalfBlocks] draws them,
        so its angles and circles are in pixels, as are any lengths it gives in cells.
        As in an element's box, the gradient spans the centers of the corner pixels, which take its end colors.
        Its `box` names one of an element's boxes, so it has no effect here.
        """
        colors = ramp(gradient).color
        indices = field_indices(gradient, width, height, 1, Region(left=0, top=0, right=width, bottom=height))
        opaque: dict[int, bytes] = {}
        for row in indices:
            for index in row:
                if index not in opaque:
                    opaque[index] = _opaque(colors(index))
        return cls(width, height, b"".join(opaque[index] for row in indices for index in row))

    @classmethod
    def from_image(cls, image: SupportsRGBA) -> Pixels:
        """The pixels of `image`, such as a Pillow `Image`, converted to RGBA."""
        rgba = image.convert("RGBA")
        width, height = rgba.size
        return cls(width, height, rgba.tobytes())

    def with_points(self, points: Mapping[Position, Color]) -> Pixels:
        """
        This picture with the pixel at each of `points` set to its color,
        which raises `ValueError` for a point outside the picture.
        """
        buffer = bytearray(self.rgba)
        for point, color in points.items():
            if not (0 <= point.x < self.width and 0 <= point.y < self.height):
                raise ValueError(f"{point} is outside a {self.width}x{self.height} picture")
            start = (point.y * self.width + point.x) * 4
            buffer[start : start + 4] = _opaque(color)
        return Pixels(self.width, self.height, bytes(buffer))


def _opaque(color: Color) -> bytes:
    """The RGBA bytes of a pixel that's `color`, wholly opaque."""
    return bytes((color.red, color.green, color.blue, 255))


type Fit = Literal["fill", "contain", "cover", "none", "scale-down"]
"""How a picture is scaled to fit its box, as CSS's `object-fit` scales an `<img>`."""


@dataclass(frozen=True, slots=True)
class HalfBlocks:
    """
    A [`Canvas`][counterweight.elements.Canvas] painter that draws `pixels` two to a cell, one above the other,
    as a half block (`▀`) whose foreground is the top pixel and whose background is the bottom one.
    A cell is about twice as tall as it is wide, so the pixels are about square,
    and its natural size is the picture's width by half its height, rounded up.

    In a box of another size, `fit` scales the picture as CSS's
    [`object-fit`](https://developer.mozilla.org/en-US/docs/Web/CSS/object-fit) does,
    and `position` places it as [`object-position`](https://developer.mozilla.org/en-US/docs/Web/CSS/object-position)
    does, as the fractions of the space left over on each axis to put to its left and above it,
    so `(0.5, 0.5)`, the default, centers it, and `(0, 0)` puts it in the top left corner.
    A picture larger than its box is cut off.

    Each cell shows the pixels nearest the middle of its two halves.
    A pixel less than half opaque is transparent, and leaves its half of the cell to show the canvas's background,
    as does a half the picture doesn't cover.
    """

    pixels: Pixels
    fit: Fit = "fill"
    position: tuple[float, float] = (0.5, 0.5)

    @property
    def natural_size(self) -> tuple[int, int]:
        return self.pixels.width, (self.pixels.height + 1) // 2

    @property
    def keeps_aspect_ratio(self) -> bool:
        return True

    def draw(self, width: int, height: int) -> Rows:
        """The cells of a `width` by `height` box that show the picture, scaled by `fit` and placed by `position`."""
        columns, rows = self.sources(width, height)
        pixel_width = self.pixels.width
        words = memoryview(self.pixels.rgba).cast("I")
        blank = (None,) * width
        drawn = []
        for top, bottom in zip(rows[::2], rows[1::2], strict=True):
            tops = blank if top is None else [None if x is None else words[top * pixel_width + x] for x in columns]
            bottoms = (
                blank if bottom is None else [None if x is None else words[bottom * pixel_width + x] for x in columns]
            )
            drawn.append(tuple(map(_half_block, tops, bottoms, strict=True)))
        return tuple(drawn)

    def pixels_at(self, cell: Position, width: int, height: int) -> tuple[Position, ...]:
        """
        The pixels of the picture shown in `cell` of a `width` by `height` box, from its top half to its bottom half,
        such as for a paint program to set the pixels under the mouse.
        There's one pixel if both halves show the same one, and none if the picture doesn't cover the cell.
        """
        if not (0 <= cell.x < width and 0 <= cell.y < height):
            return ()
        columns, rows = self.sources(width, height)
        if (x := columns[cell.x]) is None:
            return ()
        shown = (Position(x, y) for y in rows[2 * cell.y : 2 * cell.y + 2] if y is not None)
        return tuple(dict.fromkeys(shown))

    def sources(self, width: int, height: int) -> tuple[tuple[int | None, ...], tuple[int | None, ...]]:
        """
        For each pixel column and pixel row of a `width` by `height` box, two pixel rows to a cell,
        the column or row of the picture it shows, or `None` where the picture doesn't cover it.
        """
        pixels = self.pixels
        box_height = 2 * height
        if pixels.width == 0 or pixels.height == 0:
            return (None,) * width, (None,) * box_height
        scale_x, scale_y = _scales(self.fit, width / pixels.width, box_height / pixels.height)
        position_x, position_y = self.position
        return (
            _axis_sources(width, pixels.width, _round(pixels.width * scale_x), position_x),
            _axis_sources(box_height, pixels.height, _round(pixels.height * scale_y), position_y),
        )


@dataclass(frozen=True, slots=True)
class HalfBlockGradient:
    """
    A [`Canvas`][counterweight.elements.Canvas] painter that fills its canvas with `gradient`,
    two pixels to a cell, as [`HalfBlocks`][counterweight.painters.HalfBlocks] draws a picture,
    which shows a gradient at twice the vertical resolution of an element's color slots.

    It draws a new picture at its box's size each time its canvas is drawn,
    so the gradient is smooth at any size, rather than a fixed picture scaled to it,
    and the canvas draws it again only when the gradient or the box's size changes.
    It has no natural size, so size its canvas with its style.
    """

    gradient: Gradient

    @property
    def natural_size(self) -> tuple[int, int]:
        return 0, 0

    @property
    def keeps_aspect_ratio(self) -> bool:
        return False

    def draw(self, width: int, height: int) -> Rows:
        """The cells of a `width` by `height` box, showing the gradient over `width` by `2 * height` pixels."""
        return HalfBlocks(Pixels.from_gradient(width, 2 * height, self.gradient)).draw(width, height)


def _scales(fit: Fit, scale_x: float, scale_y: float) -> tuple[float, float]:
    """How much `fit` scales a picture on each axis, given the scales that would make it fill its box on each."""
    match fit:
        case "fill":
            return scale_x, scale_y
        case "contain":
            scale = min(scale_x, scale_y)
        case "cover":
            scale = max(scale_x, scale_y)
        case "none":
            scale = 1
        case "scale-down":
            scale = min(1, scale_x, scale_y)
        case _ as unreachable:
            assert_never(unreachable)
    return scale, scale


def _round(value: float) -> int:
    """
    `value` rounded to the nearest whole number, with halves rounded down rather than to even, as `round` does,
    so a centered picture with an odd number of pixels left over has the odd one after it, below or to its right,
    which puts the half cell an odd-height picture leaves over at its natural size at its bottom.
    """
    return ceil(value - 0.5)


@lru_cache(maxsize=2**8)
def _axis_sources(box: int, picture: int, scaled: int, position: float) -> tuple[int | None, ...]:
    """
    For each pixel along one axis of a box `box` pixels long, the pixel of a picture `picture` pixels long it shows,
    when the picture is scaled to `scaled` pixels and placed `position` of the way along the space left over,
    or `None` where the picture doesn't reach.
    """
    offset = _round((box - scaled) * position)
    # The source pixel nearest the middle of each scaled pixel, (p + 1/2) * picture / scaled, in whole numbers.
    return tuple(
        (2 * (b - offset) + 1) * picture // (2 * scaled) if 0 <= b - offset < scaled else None for b in range(box)
    )


@lru_cache(maxsize=2**12)
def _half_block(top: int | None, bottom: int | None) -> StyledGrapheme:
    """
    The cell that shows a `top` and a `bottom` pixel, each four RGBA bytes read as one native-order integer,
    or `None` where the picture doesn't cover it.
    A transparent pixel can only be a background, which the canvas fills in,
    so a cell with a transparent top is a lower half block (`▄`) in the bottom pixel's color.
    """
    top_color = _color(top)
    bottom_color = _color(bottom)
    if top_color is None:
        if bottom_color is None:
            return StyledGrapheme(grapheme=" ")
        return StyledGrapheme(grapheme="▄", style=CellStyle(foreground=bottom_color))
    if bottom_color is None:
        return StyledGrapheme(grapheme="▀", style=CellStyle(foreground=top_color))
    return StyledGrapheme(grapheme="▀", style=CellStyle(foreground=top_color, background=bottom_color))


def _color(word: int | None) -> Color | None:
    """The color of a pixel's RGBA bytes, read as one native-order integer, or `None` if it's less than half opaque."""
    if word is None:
        return None
    red, green, blue, alpha = word.to_bytes(4, sys.byteorder)
    return Color(red, green, blue) if alpha >= 128 else None


__all__ = ["Fit", "HalfBlockGradient", "HalfBlocks", "Pixels", "SupportsRGBA"]
