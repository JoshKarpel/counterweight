from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

import pytest
import waxy

from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.gradients import linear_gradient
from counterweight.gradients import radial_gradient
from counterweight.painters._pixels import Fit
from counterweight.painters._pixels import HalfBlockGradient
from counterweight.painters._pixels import HalfBlocks
from counterweight.painters._pixels import Pixels
from counterweight.styles import CellStyle
from counterweight.styles._styles import Color

RED = Color.from_name("red")
GREEN = Color.from_name("green")
BLUE = Color.from_name("blue")
WHITE = Color.from_name("white")


def picture(*rows: tuple[Color | None, ...]) -> Pixels:
    """A picture with a pixel of each color in `rows`, and a transparent one for each `None`."""
    rgba = b"".join(
        bytes((0, 0, 0, 0)) if color is None else bytes((*color, 255)) for colors in rows for color in colors
    )
    return Pixels(len(rows[0]), len(rows), rgba)


def upper(top: Color, bottom: Color | None = None) -> StyledGrapheme:
    style = CellStyle(foreground=top) if bottom is None else CellStyle(foreground=top, background=bottom)
    return StyledGrapheme(grapheme="▀", style=style)


def lower(bottom: Color) -> StyledGrapheme:
    return StyledGrapheme(grapheme="▄", style=CellStyle(foreground=bottom))


EMPTY = StyledGrapheme(grapheme=" ")


@pytest.mark.parametrize(("width", "height", "length"), [(2, 3, 23), (2, 3, 25), (0, 1, 4)])
def test_pixels_raise_unless_they_have_four_bytes_for_each_pixel(width: int, height: int, length: int) -> None:
    with pytest.raises(
        ValueError, match=rf"{width}x{height} picture has {width * height * 4} bytes of RGBA, not {length}"
    ):
        Pixels(width, height, bytes(length))


@pytest.mark.parametrize(("width", "height"), [(-1, 2), (2, -1)])
def test_pixels_raise_for_a_negative_size(width: int, height: int) -> None:
    with pytest.raises(ValueError, match=rf"can't be {width}x{height} pixels"):
        Pixels(width, height, b"")


def test_pixels_repr_leaves_out_their_bytes() -> None:
    assert repr(Pixels.blank(2, 3, RED)) == "Pixels(width=2, height=3)"


def test_blank_pixels_are_all_one_opaque_color() -> None:
    assert Pixels.blank(2, 1, RED) == picture((RED, RED))


def test_pixels_from_points_are_the_default_color_but_for_the_points() -> None:
    assert Pixels.from_points(2, 2, {Position(1, 0): RED, Position(0, 1): GREEN}, default=BLUE) == picture(
        (BLUE, RED),
        (GREEN, BLUE),
    )


def test_pixels_with_points_are_new_pixels_and_leave_the_original_alone() -> None:
    original = Pixels.blank(2, 1, BLUE)

    changed = original.with_points({Position(0, 0): RED})

    assert (original, changed) == (picture((BLUE, BLUE)), picture((RED, BLUE)))


@pytest.mark.parametrize("point", [Position(-1, 0), Position(0, -1), Position(2, 0), Position(0, 3)])
def test_pixels_with_a_point_outside_them_raise(point: Position) -> None:
    with pytest.raises(ValueError, match=r"outside a 2x3 picture"):
        Pixels.blank(2, 3, RED).with_points({point: GREEN})


@dataclass(frozen=True)
class FakeImage:
    """Stands in for a Pillow image: its size and bytes, and the modes it's converted to."""

    size: tuple[int, int]
    rgba: bytes
    conversions: list[str] = field(default_factory=list)

    def convert(self, mode: str) -> FakeImage:
        self.conversions.append(mode)
        return self

    def tobytes(self) -> bytes:
        return self.rgba


def test_pixels_from_an_image_are_its_size_and_its_bytes_in_rgba() -> None:
    image = FakeImage(size=(2, 1), rgba=bytes((1, 2, 3, 4, 5, 6, 7, 8)))

    assert (Pixels.from_image(image), image.conversions) == (Pixels(2, 1, bytes((1, 2, 3, 4, 5, 6, 7, 8))), ["RGBA"])


@pytest.mark.parametrize(("height", "cells"), [(4, 2), (3, 2), (1, 1), (0, 0)])
def test_half_blocks_natural_size_is_the_pictures_width_by_half_its_height_rounded_up(height: int, cells: int) -> None:
    assert HalfBlocks(Pixels.blank(3, height, RED)).natural_size == (3, cells)


def test_half_blocks_keep_their_aspect_ratio() -> None:
    assert HalfBlocks(Pixels.blank(3, 3, RED)).keeps_aspect_ratio


def test_half_blocks_draw_each_pair_of_pixel_rows_as_one_row_of_cells() -> None:
    pixels = picture(
        (RED, GREEN),
        (BLUE, WHITE),
        (GREEN, RED),
        (WHITE, BLUE),
    )

    assert HalfBlocks(pixels).draw(2, 2) == (
        (upper(RED, BLUE), upper(GREEN, WHITE)),
        (upper(GREEN, WHITE), upper(RED, BLUE)),
    )


def test_half_blocks_leave_transparent_halves_unset() -> None:
    pixels = picture(
        (RED, None, None),
        (None, GREEN, None),
    )

    assert HalfBlocks(pixels).draw(3, 1) == ((upper(RED), lower(GREEN), EMPTY),)


@pytest.mark.parametrize(("alpha", "expected"), [(127, EMPTY), (128, upper(RED))])
def test_half_blocks_treat_pixels_under_half_opaque_as_transparent(alpha: int, expected: StyledGrapheme) -> None:
    pixels = Pixels(1, 2, bytes((*RED, alpha, 0, 0, 0, 0)))

    assert HalfBlocks(pixels).draw(1, 1) == ((expected,),)


@pytest.mark.parametrize(
    ("fit", "expected"),
    [
        ("fill", (upper(RED, RED), upper(RED, GREEN))),
        ("cover", (upper(RED, RED), upper(RED, GREEN))),
        ("contain", (upper(RED, RED), upper(GREEN))),
        ("none", (upper(RED, RED), upper(GREEN))),
        ("scale-down", (upper(RED, RED), upper(GREEN))),
    ],
)
def test_half_blocks_with_an_odd_height_cover_their_last_half_cell_only_if_they_stretch_to_it(
    fit: Fit, expected: tuple[StyledGrapheme, ...]
) -> None:
    pixels = picture((RED,), (RED,), (GREEN,))

    assert HalfBlocks(pixels, fit=fit).draw(1, 2) == tuple((cell,) for cell in expected)


@pytest.mark.parametrize(("width", "height"), [(0, 0), (0, 3), (3, 0)])
def test_half_blocks_of_an_empty_picture_draw_nothing_in_their_box(width: int, height: int) -> None:
    assert HalfBlocks(Pixels(width, height, b"")).draw(2, 1) == ((EMPTY, EMPTY),)


def test_half_blocks_draw_nothing_beside_a_picture_narrower_than_their_box() -> None:
    pixels = picture((RED,), (GREEN,))

    assert HalfBlocks(pixels, fit="none").draw(3, 1) == ((EMPTY, upper(RED, GREEN), EMPTY),)


# A 2x2 picture in a 4x1 box, which is 4x2 pixels: twice as wide as the picture, and as tall.
@pytest.mark.parametrize(
    ("fit", "columns", "rows"),
    [
        ("fill", (0, 0, 1, 1), (0, 1)),
        ("contain", (None, 0, 1, None), (0, 1)),
        ("cover", (0, 0, 1, 1), (0, 1)),
        ("none", (None, 0, 1, None), (0, 1)),
        ("scale-down", (None, 0, 1, None), (0, 1)),
    ],
)
def test_half_blocks_fit_a_smaller_picture_to_their_box(
    fit: Fit, columns: tuple[int | None, ...], rows: tuple[int | None, ...]
) -> None:
    assert HalfBlocks(Pixels.blank(2, 2, RED), fit=fit).sources(4, 1) == (columns, rows)


# A 4x4 picture in a 2x1 box, which is 2x2 pixels: half as wide as the picture, and half as tall.
@pytest.mark.parametrize(
    ("fit", "columns", "rows"),
    [
        ("fill", (1, 3), (1, 3)),
        ("contain", (1, 3), (1, 3)),
        ("cover", (1, 3), (1, 3)),
        ("none", (1, 2), (1, 2)),
        ("scale-down", (1, 3), (1, 3)),
    ],
)
def test_half_blocks_fit_a_larger_picture_to_their_box(
    fit: Fit, columns: tuple[int | None, ...], rows: tuple[int | None, ...]
) -> None:
    assert HalfBlocks(Pixels.blank(4, 4, RED), fit=fit).sources(2, 1) == (columns, rows)


# A 4x2 picture in a 4x2 box, which is 4x4 pixels: as wide as the picture, and twice as tall.
@pytest.mark.parametrize(
    ("fit", "columns", "rows"),
    [
        ("contain", (0, 1, 2, 3), (None, 0, 1, None)),
        ("cover", (1, 2), (0, 0, 1, 1)),
    ],
)
def test_half_blocks_contain_and_cover_scale_both_axes_alike(
    fit: Fit, columns: tuple[int | None, ...], rows: tuple[int | None, ...]
) -> None:
    sources = HalfBlocks(Pixels.blank(4, 2, RED), fit=fit).sources(4 if fit == "contain" else 2, 2)

    assert sources == (columns, rows)


@pytest.mark.parametrize(
    ("size", "box", "columns", "rows"),
    [
        ((1, 1), (4, 2), (None, 0, None, None), (None, 0, None, None)),
        ((4, 2), (2, 2), (1, 3), (None, 1, None, None)),
        ((2, 8), (4, 2), (None, 1, None, None), (1, 3, 5, 7)),
    ],
    ids=["smaller on both axes", "wider than the box", "taller than the box"],
)
def test_half_blocks_scale_down_shrinks_a_picture_to_fit_its_box_but_never_enlarges_it(
    size: tuple[int, int],
    box: tuple[int, int],
    columns: tuple[int | None, ...],
    rows: tuple[int | None, ...],
) -> None:
    assert HalfBlocks(Pixels.blank(*size, RED), fit="scale-down").sources(*box) == (columns, rows)


@pytest.mark.parametrize(
    ("position", "columns", "rows"),
    [
        ((0, 0), (0, None, None, None), (0, None, None, None)),
        ((1, 1), (None, None, None, 0), (None, None, None, 0)),
        ((0.5, 0), (None, 0, None, None), (0, None, None, None)),
        ((0.25, 1), (None, 0, None, None), (None, None, None, 0)),
    ],
)
def test_half_blocks_place_a_picture_smaller_than_their_box_at_their_position(
    position: tuple[float, float], columns: tuple[int | None, ...], rows: tuple[int | None, ...]
) -> None:
    assert HalfBlocks(Pixels.blank(1, 1, RED), fit="none", position=position).sources(4, 2) == (columns, rows)


@pytest.mark.parametrize(
    ("position", "columns"),
    [((0, 0.5), (0, 1)), ((1, 0.5), (2, 3)), ((0.5, 0.5), (1, 2))],
)
def test_half_blocks_crop_a_picture_larger_than_their_box_at_their_position(
    position: tuple[float, float], columns: tuple[int | None, ...]
) -> None:
    assert HalfBlocks(Pixels.blank(4, 1, RED), fit="none", position=position).sources(2, 1)[0] == columns


def test_half_blocks_draw_their_whole_box() -> None:
    drawn = HalfBlocks(Pixels.blank(1, 1, RED), fit="none").draw(3, 2)

    assert [len(row) for row in drawn] == [3, 3]


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        (Position(0, 0), (Position(0, 0), Position(0, 1))),
        (Position(1, 1), (Position(1, 2),)),
        (Position(2, 0), ()),
        (Position(-1, 0), ()),
        (Position(0, 2), ()),
    ],
    ids=[
        "two pixels",
        "one pixel and a half the picture doesn't cover",
        "right of the box",
        "left of the box",
        "below the box",
    ],
)
def test_half_blocks_find_the_pixels_a_cell_shows(cell: Position, expected: tuple[Position, ...]) -> None:
    assert HalfBlocks(Pixels.blank(2, 3, RED), fit="none", position=(0, 0)).pixels_at(cell, 2, 2) == expected


def test_half_blocks_find_only_the_two_pixels_of_a_cell_with_more_rows_below_it() -> None:
    pixels = Pixels.blank(2, 6, RED)

    assert HalfBlocks(pixels, fit="none").pixels_at(Position(1, 1), 2, 3) == (Position(1, 2), Position(1, 3))


def test_half_blocks_find_one_pixel_for_a_cell_whose_halves_show_the_same_pixel() -> None:
    assert HalfBlocks(Pixels.blank(1, 1, RED)).pixels_at(Position(0, 0), 2, 1) == (Position(0, 0),)


def test_half_blocks_find_no_pixels_where_the_picture_does_not_cover_a_cell() -> None:
    assert HalfBlocks(Pixels.blank(1, 2, RED), fit="contain").pixels_at(Position(0, 0), 3, 1) == ()


GRAY = Color(128, 128, 128)
BLACK_TO_WHITE = linear_gradient(Color(0, 0, 0), Color(255, 255, 255), to="bottom right", interpolation="srgb")


@pytest.mark.parametrize(("width", "height"), [(2, 2), (5, 3), (3, 7)])
def test_a_gradients_corner_pixels_take_its_end_colors(width: int, height: int) -> None:
    pixels = Pixels.from_gradient(width, height, BLACK_TO_WHITE)
    assert (pixel(pixels, 0, 0), pixel(pixels, width - 1, height - 1)) == (Color(0, 0, 0), Color(255, 255, 255))


def test_a_gradient_picture_takes_its_pixels_as_square() -> None:
    # A circle of radius 2 pixels reaches 2 pixels in every direction, where a cell's would reach 1 row.
    gradient = radial_gradient(Color(0, 0, 0), Color(255, 255, 255), size=waxy.Length(2), interpolation="srgb")
    pixels = Pixels.from_gradient(5, 5, gradient)
    assert [pixel(pixels, 2, y) for y in range(5)] == [
        Color(255, 255, 255),
        GRAY,
        Color(0, 0, 0),
        GRAY,
        Color(255, 255, 255),
    ]


def test_an_empty_gradient_picture_has_no_pixels() -> None:
    assert Pixels.from_gradient(0, 3, BLACK_TO_WHITE) == Pixels(0, 3, b"")


def pixel(pixels: Pixels, x: int, y: int) -> Color:
    start = (y * pixels.width + x) * 4
    red, green, blue, alpha = pixels.rgba[start : start + 4]
    assert alpha == 255
    return Color(red, green, blue)


def test_a_half_block_gradient_draws_two_pixels_of_its_gradient_to_a_cell() -> None:
    gradient = linear_gradient(Color(0, 0, 0), Color(255, 255, 255), interpolation="srgb")
    assert HalfBlockGradient(gradient).draw(2, 2) == HalfBlocks(Pixels.from_gradient(2, 4, gradient)).draw(2, 2)


def test_a_half_block_gradient_shows_its_end_colors_in_its_corner_halves() -> None:
    (top, *_), *_, (*_, bottom) = HalfBlockGradient(BLACK_TO_WHITE).draw(3, 2)
    assert (top.style.foreground, bottom.style.background) == (Color(0, 0, 0), Color(255, 255, 255))


def test_a_half_block_gradient_has_no_natural_size_and_no_ratio_to_keep() -> None:
    painter = HalfBlockGradient(BLACK_TO_WHITE)
    assert (painter.natural_size, painter.keeps_aspect_ratio) == ((0, 0), False)
