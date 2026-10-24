#!/usr/bin/env python3
"""
Draws counterweight's logo into `docs/assets/logo/`: the wordmark (`counter`, a line falling one terminal cell per row,
then `weight` a row lower) for dark and light backgrounds, and the `c╱w` favicon,
whose PNGs `icons` draws for `mkdocs_hooks/logo_icons.py` to add to the docs site.

The letters are JetBrains Mono's outlines (from `codegen/fonts/`, version 2.304) rather than text,
because docs pages and READMEs show these files as images, which can't load fonts.
The SVGs and PNGs are drawn from the same `Drawing`, so they can't disagree about where anything is.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from counterweight.styles._styles import Color
from counterweight.styles.utilities import sky_400
from counterweight.styles.utilities import sky_600
from counterweight.styles.utilities import slate_100
from counterweight.styles.utilities import slate_900

FONT = Path(__file__).parent / "fonts" / "JetBrainsMono[wght].ttf"
ASSETS = Path(__file__).parent.parent / "docs" / "assets" / "logo"

LIGHT = 300
BOLD = 700

# Matches the stems of JetBrains Mono Bold, in ems.
LINE_WIDTH = 0.107

# Cells between each word of the wordmark and the line.
AIR = 0.35

ICON_SIZE = 64
ICON_RADIUS = 14
# Measured from the cells, not the ink, so the letters' side bearings add to it.
ICON_MARGIN = 3
# The favicon's line is heavier than the wordmark's, so it survives being drawn 16 pixels tall.
ICON_LINE_WIDTH = LINE_WIDTH * 1.35
# In letters: narrower cells make the letters larger in the tile, but crowd them against the line.
ICON_CELL_WIDTH = 1.1
# Keeps the line's ends off the tile's rounded corners.
ICON_LINE_INSET = 0.2

# Pillow antialiases the line's edges only by drawing larger and scaling down.
SUPERSAMPLING = 8

type Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Word:
    """A word on the cell grid, starting in `column` (fractional columns nudge it off the grid) on `row`."""

    text: str
    column: float
    row: int
    weight: int


@dataclass(frozen=True, slots=True)
class Mark:
    """
    Words on a grid of cells, and the line that falls from the top right corner of the cell before
    `line_column` one cell to the left per row, for `line_rows` rows, as the box-drawing character `╱` does.
    `left` and `right` are the columns the mark spans.
    Cells are `cell_width` letters wide and `row_height` cells tall, with each letter centered in its cell:
    a terminal's cells are one letter wide and two cells tall.
    `line_inset` shortens each end of the line by that fraction of a row.
    """

    words: tuple[Word, ...]
    line_column: int
    line_rows: int
    line_width: float
    line_inset: float
    left: float
    right: float
    cell_width: float
    row_height: float


@dataclass(frozen=True, slots=True)
class Glyph:
    """A character to draw with its origin at `origin`, in font units with y pointing down."""

    character: str
    weight: int
    origin: Point


@dataclass(frozen=True, slots=True)
class Drawing:
    """A `Mark` laid out in font units, in a `width` by `height` box with its origin at the top left."""

    glyphs: tuple[Glyph, ...]
    line: tuple[Point, Point, Point, Point]
    width: float
    height: float
    units_per_em: int


@dataclass(frozen=True, slots=True)
class Colors:
    letters: Color
    line: Color


@dataclass(frozen=True, slots=True)
class Placement:
    """Scales a `Drawing`'s font units by `scale`, then moves them by `offset`."""

    scale: float
    offset: Point

    def __call__(self, point: Point) -> Point:
        x, y = point
        return self.offset[0] + x * self.scale, self.offset[1] + y * self.scale


@dataclass(frozen=True, slots=True)
class Metrics:
    units_per_em: int
    cell_width: int
    x_height: int

    @classmethod
    def of(cls, font: TTFont) -> Metrics:
        return cls(
            units_per_em=font["head"].unitsPerEm,
            cell_width=font["hmtx"][font.getBestCmap()[ord("0")]][0],
            x_height=font["OS/2"].sxHeight,
        )


WORDMARK = Mark(
    words=(Word("counter", -AIR, 0, LIGHT), Word("weight", 7 + AIR, 1, BOLD)),
    line_column=8,
    line_rows=2,
    line_width=LINE_WIDTH,
    line_inset=0,
    left=-AIR,
    right=13 + AIR,
    cell_width=1,
    row_height=2,
)

# `c` and `w` on either side of a diagonal across a square of four square cells.
MONOGRAM = Mark(
    words=(Word("c", 0, 0, LIGHT), Word("w", 1, 1, BOLD)),
    line_column=2,
    line_rows=2,
    line_width=ICON_LINE_WIDTH,
    line_inset=ICON_LINE_INSET,
    left=0,
    right=2,
    cell_width=ICON_CELL_WIDTH,
    row_height=1,
)

ON_DARK = Colors(letters=slate_100, line=sky_400)
ON_LIGHT = Colors(letters=slate_900, line=sky_600)
TILE = slate_900


def hex_color(color: Color) -> str:
    return f"#{color.red:02x}{color.green:02x}{color.blue:02x}"


def layout(mark: Mark, metrics: Metrics) -> Drawing:
    """Places a mark's letters and line, with each row's x-height centered in it."""
    letter = metrics.cell_width
    cell = mark.cell_width * letter
    row_height = mark.row_height * cell

    def baseline(row: int) -> float:
        return row * row_height + (row_height + metrics.x_height) / 2

    glyphs = tuple(
        Glyph(character, word.weight, ((word.column - mark.left + index + 0.5) * cell - letter / 2, baseline(word.row)))
        for word in mark.words
        for index, character in enumerate(word.text)
    )

    def on_line(rows_down: float) -> Point:
        return (mark.line_column - rows_down - mark.left) * cell, rows_down * row_height

    top = on_line(mark.line_inset)
    bottom = on_line(mark.line_rows - mark.line_inset)
    rows = max(mark.line_rows, *(word.row + 1 for word in mark.words))
    return Drawing(
        glyphs=glyphs,
        line=thick_line(top, bottom, mark.line_width * metrics.units_per_em),
        width=(mark.right - mark.left) * cell,
        height=rows * row_height,
        units_per_em=metrics.units_per_em,
    )


def thick_line(start: Point, end: Point, width: float) -> tuple[Point, Point, Point, Point]:
    """The corners of a line from `start` to `end` with square-cut ends, as a polygon, so SVG and Pillow fill the same shape."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    return (
        (start[0] + nx, start[1] + ny),
        (end[0] + nx, end[1] + ny),
        (end[0] - nx, end[1] - ny),
        (start[0] - nx, start[1] - ny),
    )


def number(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def svg_paths(drawing: Drawing, outlines: dict[int, TTFont], colors: Colors, place: Placement, decimals: int) -> str:
    """The drawing's letters as one path and its line as another, with every point moved by `place`."""
    pen = SVGPathPen(None, ntos=lambda value: number(value, decimals))
    for glyph in drawing.glyphs:
        font = outlines[glyph.weight]
        x, y = place(glyph.origin)
        # Some glyphs (such as `w`) are built from components, which only the glyph set of their own weight can resolve.
        glyph_set = font.getGlyphSet()
        recording = DecomposingRecordingPen(glyph_set)
        glyph_set[font.getBestCmap()[ord(glyph.character)]].draw(recording)
        recording.replay(TransformPen(pen, (place.scale, 0, 0, -place.scale, x, y)))
    line = " ".join(f"{number(x, decimals)},{number(y, decimals)}" for x, y in map(place, drawing.line))
    return (
        f'<path fill="{hex_color(colors.letters)}" d="{pen.getCommands()}"/>'
        f'<path fill="{hex_color(colors.line)}" d="M{line}Z"/>'
    )


def wordmark_svg(drawing: Drawing, outlines: dict[int, TTFont], colors: Colors, pixels_per_em: int) -> str:
    """The wordmark, cropped to its cells, sized `pixels_per_em` unless the page sizes it."""
    scale = pixels_per_em / drawing.units_per_em
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {number(drawing.width, 1)} {number(drawing.height, 1)}" '
        f'width="{number(drawing.width * scale, 1)}" height="{number(drawing.height * scale, 1)}" role="img" aria-label="Counterweight">'
        f"<title>Counterweight</title>"
        f"{svg_paths(drawing, outlines, colors, Placement(1, (0, 0)), 1)}"
        f"</svg>\n"
    )


def icon_placement(drawing: Drawing) -> Placement:
    """Fits a drawing's cells inside the tile's margin, centered, in a square `ICON_SIZE` units wide."""
    room = ICON_SIZE - 2 * ICON_MARGIN
    scale = room / max(drawing.width, drawing.height)
    return Placement(
        scale,
        (ICON_MARGIN + (room - drawing.width * scale) / 2, ICON_MARGIN + (room - drawing.height * scale) / 2),
    )


def icon_svg(drawing: Drawing, outlines: dict[int, TTFont], place: Placement) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ICON_SIZE} {ICON_SIZE}" role="img" aria-label="Counterweight">'
        f'<rect width="{ICON_SIZE}" height="{ICON_SIZE}" rx="{ICON_RADIUS}" fill="{hex_color(TILE)}"/>'
        f"{svg_paths(drawing, outlines, ON_DARK, place, 2)}"
        f"</svg>\n"
    )


def icon_png(drawing: Drawing, place: Placement, pixels: int, radius: float) -> Image.Image:
    """The favicon at `pixels` square, with Pillow drawing the letters from the same font file the SVG outlines."""
    size = pixels * SUPERSAMPLING
    zoom = size / ICON_SIZE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius * zoom, fill=TILE)

    fonts: dict[int, ImageFont.FreeTypeFont] = {}
    for weight in {glyph.weight for glyph in drawing.glyphs}:
        font = ImageFont.truetype(FONT, size=round(drawing.units_per_em * place.scale * zoom))
        font.set_variation_by_axes([weight])
        fonts[weight] = font
    for glyph in drawing.glyphs:
        x, y = place(glyph.origin)
        draw.text((x * zoom, y * zoom), glyph.character, font=fonts[glyph.weight], anchor="ls", fill=ON_DARK.letters)
    draw.polygon([(x * zoom, y * zoom) for x, y in map(place, drawing.line)], fill=ON_DARK.line)

    return image.resize((pixels, pixels), Image.Resampling.LANCZOS)


def light_font() -> TTFont:
    return instantiateVariableFont(TTFont(FONT), {"wght": LIGHT})


def icons() -> dict[str, Image.Image]:
    """
    The favicon's PNGs, by file name.
    The docs build adds them to the site rather than the repository holding them:
    Pillow's wheels compress with a different zlib-ng build on each platform,
    so the same pixels encode to different bytes on macOS than on Linux.
    """
    monogram = layout(MONOGRAM, Metrics.of(light_font()))
    place = icon_placement(monogram)
    return {
        "favicon.png": icon_png(monogram, place, pixels=32, radius=ICON_RADIUS),
        # iOS rounds the corners of a touch icon itself, so it gets a square tile.
        "apple-touch-icon.png": icon_png(monogram, place, pixels=180, radius=0),
    }


def main() -> None:
    outlines = {LIGHT: light_font(), BOLD: instantiateVariableFont(TTFont(FONT), {"wght": BOLD})}
    metrics = Metrics.of(outlines[LIGHT])

    wordmark = layout(WORDMARK, metrics)
    (ASSETS / "wordmark-dark.svg").write_text(wordmark_svg(wordmark, outlines, ON_DARK, pixels_per_em=40))
    (ASSETS / "wordmark-light.svg").write_text(wordmark_svg(wordmark, outlines, ON_LIGHT, pixels_per_em=40))

    monogram = layout(MONOGRAM, metrics)
    (ASSETS / "favicon.svg").write_text(icon_svg(monogram, outlines, icon_placement(monogram)))


if __name__ == "__main__":
    main()
