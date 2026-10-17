from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import AnyElement
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Region
from counterweight.hooks.impls import NodeKey
from counterweight.layout import LayoutTree
from counterweight.output import Frame
from counterweight.paint import Paint
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.styles import Color
from counterweight.styles.utilities import align_children_start
from counterweight.styles.utilities import border
from counterweight.styles.utilities import col
from counterweight.styles.utilities import content_color
from counterweight.styles.utilities import height
from counterweight.styles.utilities import max_width
from counterweight.styles.utilities import min_width
from counterweight.styles.utilities import overflow_hidden
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import row
from counterweight.styles.utilities import size
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_justify_right
from counterweight.styles.utilities import width

GREEN = Color.from_name("green")


@dataclass(frozen=True, slots=True)
class Solid:
    """A painter that fills whatever box it's given with `grapheme`."""

    grapheme: str = "a"
    natural_size: tuple[int, int] = (3, 2)
    keeps_aspect_ratio: bool = False

    def draw(self, width: int, height: int) -> Rows:
        return ((StyledGrapheme(grapheme=self.grapheme),) * width,) * height


@dataclass(frozen=True, slots=True)
class Fixed:
    """A painter that draws `rows` whatever box it's given."""

    rows: Rows
    natural_size: tuple[int, int] = (3, 2)
    keeps_aspect_ratio: bool = False

    def draw(self, width: int, height: int) -> Rows:
        return self.rows


@dataclass(frozen=True, slots=True)
class Counted:
    """A painter that records the size of each box it draws, which isn't part of what it's compared by."""

    grapheme: str = "a"
    sizes: list[tuple[int, int]] = field(default_factory=list, compare=False)
    natural_size: tuple[int, int] = (3, 2)
    keeps_aspect_ratio: bool = False

    def draw(self, width: int, height: int) -> Rows:
        self.sizes.append((width, height))
        return ((StyledGrapheme(grapheme=self.grapheme),) * width,) * height


async def render(root: AnyElement, dimensions: tuple[int, int] = (6, 4)) -> Paint:
    frames: list[Frame] = []

    @component
    def screen() -> AnyElement:
        return root

    await app(
        screen(),
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot(handler=frames.append), Quit()],
        check_purity=True,
    )
    return frames[0].paint


def graphemes(paint: Paint) -> list[str]:
    return ["".join(cell.grapheme for cell in row) for row in paint.rows()]


def top_left(canvas: Canvas) -> Div:
    """`canvas` at its own size in the top left corner, which a column that doesn't stretch its children leaves it."""
    return Div(style=col | align_children_start, children=(canvas,))


def test_canvases_have_no_children() -> None:
    assert Canvas(painter=Solid()).children == ()


@pytest.mark.parametrize(
    ("style", "keeps_aspect_ratio", "expected"),
    [
        (Style(), True, ["aaaa  ", "aaaa  ", "      ", "      "]),
        (width(2), True, ["aa    ", "      ", "      ", "      "]),
        (height(1), True, ["aa    ", "      ", "      ", "      "]),
        (width(4) | border, True, ["┌──┐  ", "│aa│  ", "└──┘  ", "      "]),
        (width(2), False, ["aa    ", "aa    ", "      ", "      "]),
    ],
    ids=[
        "natural size",
        "width keeps the ratio",
        "height keeps the ratio",
        "width keeps the ratio of the content box",
        "width without a ratio",
    ],
)
async def test_canvas_takes_its_natural_size_on_each_axis_its_style_leaves_undetermined(
    style: Style, keeps_aspect_ratio: bool, expected: list[str]
) -> None:
    painter = Solid(natural_size=(4, 2), keeps_aspect_ratio=keeps_aspect_ratio)

    assert graphemes(await render(top_left(Canvas(painter=painter, style=style)))) == expected


async def test_canvas_in_a_column_that_stretches_it_keeps_its_ratio_at_its_max_width() -> None:
    painter = Solid(natural_size=(4, 2), keeps_aspect_ratio=True)

    paint = await render(Div(style=col, children=(Canvas(painter=painter, style=max_width(2)),)))

    assert graphemes(paint) == ["aa    ", "      ", "      ", "      "]


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (Style(), ["aaaaaa", "aaaaaa", "      ", "      "]),
        (min_width(0), ["aaa   ", "      ", "      ", "      "]),
    ],
    ids=["floored at its natural width", "shrinks with min_width(0), keeping its ratio"],
)
async def test_canvas_in_a_narrow_row_shrinks_only_with_min_width_zero(style: Style, expected: list[str]) -> None:
    painter = Solid(natural_size=(6, 2), keeps_aspect_ratio=True)

    paint = await render(
        Div(
            style=col | align_children_start,
            children=(Div(style=row | width(3), children=(Canvas(painter=painter, style=style),)),),
        )
    )

    assert graphemes(paint) == expected


async def test_canvas_with_no_natural_size_and_no_styled_size_is_not_drawn() -> None:
    painter = Counted(natural_size=(0, 0))

    await render(top_left(Canvas(painter=painter)))

    assert painter.sizes == []


@pytest.mark.parametrize("natural_size", [(0, 0), (0, 3), (3, 0)])
@pytest.mark.parametrize("keeps_aspect_ratio", [True, False])
async def test_canvas_with_no_natural_size_takes_its_styled_size(
    natural_size: tuple[int, int], keeps_aspect_ratio: bool
) -> None:
    painter = Solid(natural_size=natural_size, keeps_aspect_ratio=keeps_aspect_ratio)

    paint = await render(top_left(Canvas(painter=painter, style=size(2, 1))))

    assert graphemes(paint)[:2] == ["aa    ", "      "]


async def test_canvas_rows_past_its_content_box_are_cut_off() -> None:
    painter = Fixed(rows=((StyledGrapheme(grapheme="x"),) * 5,) * 3)

    paint = await render(top_left(Canvas(painter=painter, style=size(4, 3) | border)), dimensions=(6, 4))

    assert graphemes(paint) == ["┌──┐  ", "│xx│  ", "└──┘  ", "      "]


async def test_canvas_rows_are_drawn_from_the_left_whatever_its_text_justify() -> None:
    painter = Fixed(rows=((StyledGrapheme(grapheme="x"),),))

    paint = await render(top_left(Canvas(painter=painter, style=size(3, 1) | text_justify_right)))

    assert graphemes(paint)[0] == "x     "


async def test_canvas_shows_its_content_color_where_its_rows_do_not_reach() -> None:
    painter = Fixed(rows=((StyledGrapheme(grapheme="x"),),))

    style = size(3, 2) | content_color("green", 500)

    paint = await render(top_left(Canvas(painter=painter, style=style)))

    assert [[cell.style.background == style.resolved.content_color for cell in row[:4]] for row in paint.rows()] == [
        [True, True, True, False],
        [True, True, True, False],
        [False, False, False, False],
        [False, False, False, False],
    ]


ONE_UPPER_HALF = Fixed(rows=((StyledGrapheme(grapheme="▀", style=CellStyle(foreground=GREEN)),),))


async def test_unset_background_of_a_cell_is_the_canvas_content_color() -> None:
    style = size(1, 1) | content_color("blue", 500)

    paint = await render(top_left(Canvas(painter=ONE_UPPER_HALF, style=style)))

    assert paint[0, 0].style.background == style.resolved.content_color


async def test_unset_background_of_a_cell_is_the_canvas_text_background_if_it_sets_one() -> None:
    style = size(1, 1) | content_color("blue", 500) | text_bg("red", 500)

    paint = await render(top_left(Canvas(painter=ONE_UPPER_HALF, style=style)))

    assert paint[0, 0].style.background == style.resolved.text_style.background


async def test_unset_foreground_of_a_cell_is_the_canvas_text_color() -> None:
    painter = Fixed(rows=((StyledGrapheme(grapheme="x"),),))

    style = size(1, 1) | text_color("red", 500)

    paint = await render(top_left(Canvas(painter=painter, style=style)))

    assert paint[0, 0].style.foreground == style.resolved.text_style.foreground


async def test_canvas_draws_a_wide_cluster_across_two_cells() -> None:
    painter = Fixed(rows=((StyledGrapheme(grapheme="日"), StyledGrapheme(grapheme="x")),))

    paint = await render(top_left(Canvas(painter=painter, style=size(3, 1))))

    assert [cell.grapheme for cell in next(paint.rows())][:4] == ["日", "", "x", " "]


async def test_canvas_whose_overflow_is_scroll_raises() -> None:
    with pytest.raises(ValueError, match="Canvas doesn't scroll its own content"):
        await render(Canvas(painter=Solid(), style=overflow_y_scroll))


async def test_canvas_outside_every_clip_is_not_drawn() -> None:
    painter = Counted()

    await render(Div(style=size(0, 0) | overflow_hidden, children=(Canvas(painter=painter),)))

    assert painter.sizes == []


KEY = NodeKey(1)


def test_canvas_is_drawn_once_while_its_painter_is_equal_and_its_box_is_the_same_size() -> None:
    tree = LayoutTree()
    painter = Counted()
    box = Region(left=1, top=1, right=4, bottom=3)

    first = tree.drawn(KEY, painter, box)
    again = tree.drawn(KEY, Counted(sizes=painter.sizes), box)

    assert (again is first, painter.sizes) == (True, [(3, 2)])


@pytest.mark.parametrize(
    ("painter", "box", "drawn"),
    [
        (Counted(), Region(left=0, top=0, right=4, bottom=2), [(3, 2), (4, 2)]),
        (Counted(), Region(left=0, top=0, right=3, bottom=1), [(3, 2), (3, 1)]),
        (Counted(grapheme="b"), Region(left=0, top=0, right=3, bottom=2), [(3, 2), (3, 2)]),
    ],
    ids=["wider", "shorter", "unequal painter"],
)
def test_canvas_is_drawn_again_when_its_painter_or_box_changes(
    painter: Counted, box: Region, drawn: list[tuple[int, int]]
) -> None:
    tree = LayoutTree()
    sizes: list[tuple[int, int]] = []
    tree.drawn(KEY, Counted(sizes=sizes), Region(left=0, top=0, right=3, bottom=2))

    tree.drawn(KEY, Counted(grapheme=painter.grapheme, sizes=sizes), box)

    assert sizes == drawn


@pytest.mark.parametrize(
    "box",
    [Region(left=2, top=2, right=2, bottom=4), Region(left=2, top=2, right=4, bottom=2)],
    ids=["no columns", "no rows"],
)
def test_canvas_with_no_cells_is_not_drawn(box: Region) -> None:
    painter = Counted()

    assert (LayoutTree().drawn(KEY, painter, box), painter.sizes) == ((), [])
