from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import assert_type

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.gradients import Gradient
from counterweight.gradients import linear_gradient
from counterweight.layout import LayoutTree
from counterweight.layout import MeasurableText
from counterweight.layout import Remove
from counterweight.output import Frame
from counterweight.paint import Cell
from counterweight.paint import NodeFields
from counterweight.paint import Paint
from counterweight.paint import paint_layout
from counterweight.styles.styles import CELL_STYLE_DEFAULTS
from counterweight.styles.styles import STYLE_DEFAULTS
from counterweight.styles.styles import AnyColor
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import IndexedColor
from counterweight.styles.styles import ResolvedCellStyle
from counterweight.styles.styles import ResolvedStyle
from counterweight.styles.styles import Style
from counterweight.styles.styles import as_solid
from counterweight.styles.styles import is_solid
from counterweight.styles.styles import is_solid_cell_style
from counterweight.styles.styles import is_solid_color
from counterweight.styles.styles import resolve_cell_style
from counterweight.styles.styles import rgb_of
from counterweight.styles.styles import with_colors
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_contract
from counterweight.styles.utilities import border_light
from counterweight.styles.utilities import border_top
from counterweight.styles.utilities import margin_y
from counterweight.styles.utilities import pad_top
from counterweight.styles.utilities import pad_y
from counterweight.styles.utilities import size

BLACK = Color(0, 0, 0)
WHITE = Color(255, 255, 255)
RED = Color(255, 0, 0)
DOWN = linear_gradient(BLACK, WHITE, interpolation="srgb")
RIGHT = linear_gradient(BLACK, WHITE, to="right", interpolation="srgb")


def gray(level: int) -> Color:
    return Color(level, level, level)


def backgrounds(paint: Paint) -> list[list[int]]:
    """The red channel of each cell's background, which is its gray level for the gradients here."""
    return [[rgb_of(cell.style.background, BLACK).red for cell in row] for row in paint.rows()]


def foregrounds(paint: Paint) -> list[list[int]]:
    return [[rgb_of(cell.style.foreground, WHITE).red for cell in row] for row in paint.rows()]


async def render(root: Div | Text | Canvas, dimensions: tuple[int, int], cell_aspect_ratio: float = 2) -> Frame:
    frames: list[Frame] = []

    @component
    def screen() -> Div:
        return Div(children=(root,))

    await app(
        screen(),
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot(handler=frames.append), Quit()],
        check_purity=True,
        cell_aspect_ratio=cell_aspect_ratio,
    )
    return frames[0]


async def test_a_content_color_gradient_maps_over_the_border_box() -> None:
    frame = await render(Div(style=size(1, 3) | margin_y(1) | Style(content_color=DOWN)), (1, 5))
    assert backgrounds(frame.paint) == [[0], [0], [128], [255], [0]]


async def test_a_margin_color_gradient_maps_over_the_margin_box() -> None:
    frame = await render(Div(style=size(1, 1) | margin_y(1) | Style(margin_color=DOWN, content_color=RED)), (1, 3))
    assert backgrounds(frame.paint) == [[0], [255], [255]]


async def test_a_padding_color_gradient_maps_over_the_padding_box() -> None:
    frame = await render(Div(style=size(1, 3) | pad_y(1) | Style(padding_color=DOWN, content_color=RED)), (1, 3))
    assert backgrounds(frame.paint) == [[0], [255], [255]]


async def test_a_gradient_maps_over_the_box_it_names() -> None:
    gradient = linear_gradient(BLACK, WHITE, interpolation="srgb", box="margin")
    frame = await render(
        Div(style=size(1, 3) | margin_y(1) | pad_y(1) | Style(padding_color=gradient, content_color=RED)), (1, 5)
    )
    assert backgrounds(frame.paint) == [[0], [64], [255], [191], [0]]


async def test_a_border_gradient_maps_its_foreground_and_background_over_the_border_box() -> None:
    style = size(3, 3) | border | border_light | Style(border_style=CellStyle(foreground=RIGHT, background=DOWN))
    frame = await render(Div(style=style), (3, 3))
    assert (foregrounds(frame.paint), backgrounds(frame.paint), frame.text(ansi=False)) == (
        [[0, 128, 255], [0, 255, 255], [0, 128, 255]],
        [[0, 0, 0], [128, 0, 128], [255, 255, 255]],
        "┌─┐\n│ │\n└─┘",
    )


async def test_a_border_gradient_beside_a_solid_color_keeps_the_solid_color() -> None:
    style = size(2, 2) | border | border_light | Style(border_style=CellStyle(foreground=RIGHT, background=RED))
    frame = await render(Div(style=style), (2, 2))
    assert {cell.style.background for cell in frame.paint.cells} == {RED}


async def test_a_text_gradient_maps_over_the_content_box() -> None:
    frame = await render(Text(content="ab", style=size(3, 1) | Style(text_style=CellStyle(foreground=RIGHT))), (3, 1))
    assert foregrounds(frame.paint) == [[0, 128, 255]]


async def test_a_chunks_gradient_continues_the_elements() -> None:
    content = (Chunk(content="ab"), Chunk(content="cd", style=CellStyle(foreground=RIGHT)))
    frame = await render(Text(content=content, style=size(4, 1)), (4, 1))
    assert foregrounds(frame.paint) == [[255, 255, 170, 255]]


async def test_a_chunks_own_color_wins_over_a_text_gradient() -> None:
    content = (Chunk(content="a", style=CellStyle(foreground=RED)), Chunk(content="bc"))
    frame = await render(
        Text(content=content, style=size(3, 1) | Style(text_style=CellStyle(foreground=RIGHT))), (3, 1)
    )
    assert [cell.style.foreground for cell in frame.paint.cells] == [RED, gray(128), WHITE]


async def test_text_overflowing_its_box_continues_the_gradient() -> None:
    frame = await render(
        Text(content="abcd\nefgh", style=size(2, 2) | Style(text_style=CellStyle(foreground=DOWN))), (4, 2)
    )
    assert foregrounds(frame.paint) == [[0, 0, 0, 0], [255, 255, 255, 255]]


async def test_a_gradient_beside_a_solid_border_keeps_the_border() -> None:
    frame = await render(Div(style=size(3, 3) | border | border_light | Style(content_color=DOWN)), (3, 3))
    assert (frame.text(ansi=False), frame.paint[1, 1].style.background) == ("┌─┐\n│ │\n└─┘", gray(128))


async def test_a_gradient_text_past_the_edge_of_the_screen_is_cut_off() -> None:
    style = size(2, 1) | Style(text_style=CellStyle(foreground=RIGHT))
    frame = await render(Text(content="abcdef", style=style), (4, 1))
    assert (frame.text(ansi=False), foregrounds(frame.paint)) == ("abcd", [[0, 255, 255, 255]])


async def test_a_gradient_text_draws_no_cell_for_a_zero_width_cluster() -> None:
    style = size(3, 1) | Style(text_style=CellStyle(foreground=RIGHT))
    frame = await render(Text(content="a\u200bbc", style=style), (3, 1))
    assert (frame.text(ansi=False), foregrounds(frame.paint)) == ("abc", [[0, 128, 255]])


async def test_a_two_cell_cluster_takes_the_gradient_at_its_first_cell() -> None:
    frame = await render(Text(content="日a", style=size(3, 1) | Style(text_style=CellStyle(background=RIGHT))), (3, 1))
    assert (backgrounds(frame.paint), [cell.grapheme for cell in frame.paint.cells]) == ([[0, 0, 255]], ["日", "", "a"])


@dataclass(frozen=True, slots=True)
class Blank:
    """A painter of spaces, in `style`, which leaves their background to the canvas unless it sets one."""

    style: CellStyle = CellStyle()

    @property
    def natural_size(self) -> tuple[int, int]:
        return 0, 0

    @property
    def keeps_aspect_ratio(self) -> bool:
        return False

    def draw(self, width: int, height: int) -> Rows:
        return ((StyledGrapheme(grapheme=" ", style=self.style),) * width,) * height


async def test_a_canvas_cell_with_no_background_shows_its_content_color_gradient_over_its_border_box() -> None:
    style = size(1, 4) | pad_top(1) | Style(content_color=DOWN, padding_color=RED)
    frame = await render(Canvas(painter=Blank(), style=style), (1, 4))
    assert backgrounds(frame.paint) == [[255], [85], [170], [255]]


async def test_a_canvas_content_color_gradient_that_names_its_box_keeps_it() -> None:
    gradient = linear_gradient(BLACK, WHITE, interpolation="srgb", box="content")
    style = size(1, 4) | pad_top(1) | Style(content_color=gradient, padding_color=RED)
    frame = await render(Canvas(painter=Blank(), style=style), (1, 4))
    assert backgrounds(frame.paint) == [[255], [0], [128], [255]]


async def test_a_painters_own_gradient_maps_over_the_content_box() -> None:
    style = size(1, 4) | pad_top(1) | Style(padding_color=RED)
    frame = await render(Canvas(painter=Blank(CellStyle(background=DOWN)), style=style), (1, 4))
    assert backgrounds(frame.paint) == [[255], [0], [128], [255]]


async def test_a_canvas_text_style_background_wins_over_its_content_color() -> None:
    style = size(1, 2) | Style(content_color=DOWN, text_style=CellStyle(background=RED))
    frame = await render(Canvas(painter=Blank(), style=style), (1, 2))
    assert {cell.style.background for cell in frame.paint.cells} == {RED}


@pytest.mark.parametrize(
    ("aspect", "expected"),
    [
        (2, [[0, 43, 85], [85, 128, 170], [170, 212, 255]]),
        (1, [[0, 64, 128], [64, 128, 191], [127, 191, 255]]),
    ],
)
async def test_angles_follow_the_cell_aspect_ratio(aspect: float, expected: list[list[int]]) -> None:
    gradient = linear_gradient(BLACK, WHITE, angle=135, interpolation="srgb")
    frame = await render(Div(style=size(3, 3) | Style(content_color=gradient)), (3, 3), cell_aspect_ratio=aspect)
    assert backgrounds(frame.paint) == expected


async def test_a_gradient_frames_svg_draws_a_rect_per_run_of_one_color() -> None:
    frame = await render(Div(style=size(3, 1) | Style(content_color=RIGHT)), (3, 1))
    fills = [line.split('fill="')[1][:7] for line in frame.svg().splitlines() if "<rect" in line]
    assert fills == ["#000000", "#000000", "#808080", "#ffffff"]


async def test_a_gradient_frames_text_has_each_cells_color() -> None:
    frame = await render(Div(style=size(3, 1) | Style(content_color=RIGHT)), (3, 1))
    assert all(f"48;2;{level};{level};{level}m" in frame.text() for level in (0, 128, 255))


SCREEN = Region(left=0, top=0, right=4, bottom=4)


def element_rects(border_box: Region, clip: Region | None = SCREEN) -> Rects:
    return Rects(
        content=border_box,
        padding=border_box,
        border=border_box,
        margin=border_box,
        clip=clip,
        visible=None if clip is None else border_box.intersection(clip),
    )


BOX = Region(left=0, top=0, right=4, bottom=4)
FILLED = Div(style=Style(content_color=DOWN))


def paint(
    element: Div | Text | Canvas,
    fields: dict[str, NodeFields],
    rects: Rects | None = None,
    lines: Rows = (),
    lines_are_solid: bool = True,
    aspect: float = 2,
) -> Paint:
    painted, _ = paint_layout(
        [("node", element, rects or element_rects(BOX), lines, lines_are_solid)], 4, 4, fields, aspect
    )
    return painted


def test_a_gradient_that_doesnt_change_reuses_its_cells() -> None:
    fields: dict[str, NodeFields] = {}
    first = paint(FILLED, fields)
    runs = fields["node"].painted["content"][1]
    second = paint(FILLED, fields)
    assert (fields["node"].painted["content"][1] is runs, second.cells) == (True, first.cells)


def test_a_gradient_that_moves_reuses_its_field() -> None:
    fields: dict[str, NodeFields] = {}
    paint(FILLED, fields, element_rects(Region(left=0, top=0, right=2, bottom=2)))
    field = fields["node"].fields[("content", DOWN)]
    moved = paint(FILLED, fields, element_rects(Region(left=2, top=2, right=4, bottom=4)))
    assert (fields["node"].fields[("content", DOWN)] is field, backgrounds(moved)[3]) == (True, [0, 0, 255, 255])


def test_a_gradient_whose_box_changes_size_rebuilds_its_field() -> None:
    fields: dict[str, NodeFields] = {}
    paint(FILLED, fields, element_rects(Region(left=0, top=0, right=2, bottom=2)))
    field = fields["node"].fields[("content", DOWN)]
    paint(FILLED, fields, element_rects(Region(left=0, top=0, right=2, bottom=3)))
    assert fields["node"].fields[("content", DOWN)] is not field


def test_a_frame_keeps_only_the_fields_it_used() -> None:
    fields: dict[str, NodeFields] = {}
    paint(FILLED, fields)
    paint(Div(style=Style(content_color=RIGHT)), fields)
    assert list(fields["node"].fields) == [("content", RIGHT)]


def text_lines(content: str, style: CellStyle) -> Rows:
    return MeasurableText.of((content, style, "none")).lines_at(None)


TEXT_STYLE = CellStyle(foreground=DOWN)
GRADIENT_TEXT = Text(content="", style=Style(text_style=TEXT_STYLE))


def test_text_that_changes_reuses_its_field() -> None:
    fields: dict[str, NodeFields] = {}
    paint(GRADIENT_TEXT, fields, lines=text_lines("ab\ncd", TEXT_STYLE), lines_are_solid=False)
    field = fields["node"].fields[("text", DOWN)]
    paint(GRADIENT_TEXT, fields, lines=text_lines("ab\ncd", TEXT_STYLE), lines_are_solid=False)
    changed = paint(GRADIENT_TEXT, fields, lines=text_lines("ef\ngh", TEXT_STYLE), lines_are_solid=False)
    assert (fields["node"].fields[("text", DOWN)] is field, changed[0, 1].grapheme) == (True, "g")


def test_a_clipped_gradient_draws_the_cells_it_would_unclipped() -> None:
    whole = paint(FILLED, {})
    clip = Region(left=1, top=1, right=3, bottom=4)
    clipped = paint(FILLED, {}, element_rects(BOX, clip))
    inside = [(x, y) for x in range(1, 3) for y in range(1, 4)]
    assert [clipped[position] for position in inside] == [whole[position] for position in inside]


def test_a_gradient_text_cut_off_on_the_left_colors_a_two_cell_cluster_where_it_shows() -> None:
    style = CellStyle(background=RIGHT)
    lines = ((StyledGrapheme(grapheme="日", style=style), StyledGrapheme(grapheme="a", style=style)),)
    rects = element_rects(Region(left=-1, top=0, right=2, bottom=1))
    painted = paint(Text(content=""), {}, rects, lines, lines_are_solid=False)
    assert (painted[0, 0].grapheme, painted[0, 0].style.background, painted[1, 0].style.background) == (
        " ",
        gray(128),
        WHITE,
    )


def test_a_gradient_element_off_the_screen_paints_nothing() -> None:
    fields: dict[str, NodeFields] = {}
    off_screen = Region(left=5, top=0, right=6, bottom=1)
    painted = paint(FILLED, fields, element_rects(off_screen, off_screen))
    assert painted.cells == Paint.blank(4, 4).cells


@pytest.mark.parametrize("clip", [None, Region(left=0, top=0, right=1, bottom=1)])
def test_a_gradient_element_outside_its_clip_paints_nothing(clip: Region | None) -> None:
    rects = element_rects(Region(left=2, top=2, right=4, bottom=4), clip)
    painted = paint(FILLED, {}, rects)
    assert painted.cells == Paint.blank(4, 4).cells


def test_a_gradient_element_with_nothing_to_draw_paints_nothing() -> None:
    painted = paint(Div(style=Style(text_style=TEXT_STYLE)), {})
    assert painted.cells == Paint.blank(4, 4).cells


def test_a_gradient_element_whose_text_is_clipped_still_draws_its_box() -> None:
    lines = text_lines("ab", TEXT_STYLE)
    clip = Region(left=0, top=1, right=4, bottom=4)
    row = Region(left=0, top=0, right=4, bottom=1)
    rects = Rects(
        content=row,
        padding=row,
        border=BOX,
        margin=BOX,
        clip=clip,
        visible=BOX.intersection(clip),
    )
    painted = paint(Text(content="ab", style=Style(content_color=DOWN)), {}, rects, lines, lines_are_solid=False)
    assert [row[0] for row in backgrounds(painted)] == [0, 85, 170, 255]


def test_removing_a_node_drops_its_fields() -> None:
    tree = LayoutTree()
    tree.fields["node"] = NodeFields()  # type: ignore[index]
    tree.nodes["node"] = tree.tree.new_leaf(Style().layout)  # type: ignore[index]
    tree.apply([Remove(key="node")])  # type: ignore[arg-type]
    assert tree.fields == {}


@pytest.mark.parametrize(
    ("content", "is_solid_text"),
    [
        ("one line", True),
        ("two\nlines", True),
        ((Chunk(content="a"), Chunk(content="b", style=CellStyle(background=DOWN))), False),
    ],
)
def test_a_text_knows_whether_its_cells_are_solid(content: str | tuple[Chunk, ...], is_solid_text: bool) -> None:
    assert MeasurableText.of((content, CellStyle(), "none")).is_solid is is_solid_text


def test_a_text_styled_with_a_gradient_isnt_solid() -> None:
    assert MeasurableText.of(("one line", TEXT_STYLE, "none")).is_solid is False


@pytest.mark.parametrize(("style", "is_solid_drawing"), [(CellStyle(), True), (TEXT_STYLE, False)])
def test_a_drawing_knows_whether_its_cells_are_solid(style: CellStyle, is_solid_drawing: bool) -> None:
    _, is_solid_rows = LayoutTree().drawn("node", Blank(style), BOX)  # type: ignore[arg-type]
    assert is_solid_rows is is_solid_drawing


@pytest.mark.parametrize(
    ("color", "expected"),
    [(RED, True), (IndexedColor(3), True), (CELL_STYLE_DEFAULTS.foreground, True), (DOWN, False)],
)
def test_a_solid_color_is_any_color_but_a_gradient(color: AnyColor | Gradient, expected: bool) -> None:
    assert is_solid_color(color) is expected


@pytest.mark.parametrize(
    ("colors", "expected"),
    [
        ({}, True),
        ({"foreground": RED, "background": IndexedColor(1)}, True),
        ({"foreground": DOWN}, False),
        ({"background": DOWN}, False),
    ],
)
def test_a_cell_style_is_solid_unless_a_color_is_a_gradient(
    colors: dict[str, AnyColor | Gradient], expected: bool
) -> None:
    # Built here rather than in the parameters, so it's built by the code under test, not when the module is collected.
    style = CellStyle(**colors)  # type: ignore[arg-type]
    assert (style.is_solid, resolve_cell_style(style).is_solid) == (expected, expected)


@pytest.mark.parametrize(
    "style",
    [
        Style(margin_color=DOWN),
        Style(padding_color=DOWN),
        Style(content_color=DOWN),
        Style(border_style=CellStyle(foreground=DOWN)),
        Style(text_style=CellStyle(background=DOWN)),
    ],
)
def test_a_style_with_a_gradient_in_any_slot_isnt_solid(style: Style) -> None:
    assert is_solid(style.resolved) is False


def test_a_style_without_gradients_is_solid() -> None:
    assert (is_solid(Style(content_color=RED).resolved), is_solid(STYLE_DEFAULTS)) == (True, True)


def test_a_resolved_style_keeps_its_gradients() -> None:
    assert Style(content_color=DOWN).resolved.content_color is DOWN


def test_a_solid_cell_style_is_itself_as_solid() -> None:
    style = resolve_cell_style(CellStyle(foreground=RED))
    assert as_solid(style) is style


def test_a_gradient_cell_style_isnt_solid() -> None:
    with pytest.raises(TypeError, match="holds a gradient"):
        as_solid(resolve_cell_style(TEXT_STYLE))


def test_with_colors_keeps_the_attributes() -> None:
    style = resolve_cell_style(CellStyle(foreground=DOWN, bold=True, link="https://example.com/"))
    assert with_colors(style, RED, BLACK) == as_solid(
        resolve_cell_style(CellStyle(foreground=RED, background=BLACK, bold=True, link="https://example.com/"))
    )


if TYPE_CHECKING:
    wide = resolve_cell_style(CellStyle())
    assert_type(wide, ResolvedCellStyle[AnyColor | Gradient])
    if is_solid_cell_style(wide):
        assert_type(wide, ResolvedCellStyle[AnyColor])
    assert_type(as_solid(wide), ResolvedCellStyle[AnyColor])
    assert_type(with_colors(wide, RED, BLACK), ResolvedCellStyle[Color])
    solid_is_wide: ResolvedCellStyle[AnyColor | Gradient] = CELL_STYLE_DEFAULTS
    Cell("x", wide)  # type: ignore[arg-type]

    resolved = Style().resolved
    assert_type(resolved, ResolvedStyle[AnyColor | Gradient])
    if is_solid(resolved):
        assert_type(resolved, ResolvedStyle[AnyColor])
        assert_type(resolved.text_style, ResolvedCellStyle[AnyColor])


def test_a_gradient_whose_box_changes_size_rebuilds_its_field_where_it_shows_the_same_cells() -> None:
    fields: dict[str, NodeFields] = {}
    clip = Region(left=0, top=0, right=4, bottom=2)
    paint(FILLED, fields, element_rects(Region(left=0, top=0, right=4, bottom=3), clip))
    taller = paint(FILLED, fields, element_rects(Region(left=0, top=0, right=4, bottom=5), clip))
    assert [row[0] for row in backgrounds(taller)] == [0, 64, 0, 0]


def test_a_gradient_drawn_at_another_aspect_ratio_rebuilds_its_field() -> None:
    fields: dict[str, NodeFields] = {}
    diagonal = Div(style=Style(content_color=linear_gradient(BLACK, WHITE, angle=135, interpolation="srgb")))
    paint(diagonal, fields)
    square = paint(diagonal, fields, aspect=1)
    assert backgrounds(square)[0] == [0, 43, 85, 128]


def boxes(margin: Region, border: Region, clip: Region = SCREEN) -> Rects:
    return Rects(
        content=border,
        padding=border,
        border=border,
        margin=margin,
        clip=clip,
        visible=border.intersection(clip),
    )


MARGIN_BORDER = Div(
    style=border
    | border_light
    | Style(
        border_style=CellStyle(foreground=linear_gradient(BLACK, WHITE, to="right", interpolation="srgb", box="margin"))
    )
)


def test_a_border_gradient_mapped_over_another_box_follows_that_box() -> None:
    fields: dict[str, NodeFields] = {}
    border_box = Region(left=1, top=0, right=3, bottom=2)
    paint(MARGIN_BORDER, fields, boxes(Region(left=0, top=0, right=4, bottom=2), border_box))
    wider = paint(MARGIN_BORDER, fields, boxes(Region(left=1, top=0, right=4, bottom=2), border_box))
    assert foregrounds(wider)[0][1:3] == [0, 128]


def test_a_border_whose_gradient_changes_is_drawn_again() -> None:
    fields: dict[str, NodeFields] = {}
    style = border | border_light
    paint(Div(style=style | Style(border_style=CellStyle(foreground=RIGHT))), fields)
    changed = paint(Div(style=style | Style(border_style=CellStyle(foreground=DOWN))), fields)
    assert [row[0] for row in foregrounds(changed)] == [0, 85, 170, 255]


def test_a_gradient_border_contracts_as_a_solid_one_does() -> None:
    style = border_top | border_contract(1) | Style(border_style=CellStyle(foreground=RIGHT))
    assert paint(Div(style=style), {})[0, 0].grapheme == " "


def test_a_clipped_gradient_border_keeps_only_the_healing_hints_inside_its_clip() -> None:
    style = border | border_light | Style(border_style=CellStyle(foreground=RIGHT))
    clip = Region(left=0, top=0, right=2, bottom=4)
    _, hints = paint_layout([("node", Div(style=style), element_rects(BOX, clip), (), True)], 4, 4, {})
    assert sorted(hints) == [Position(0, 0), Position(0, 3)]


def test_text_overflowing_into_the_clip_from_a_box_outside_it_is_drawn() -> None:
    text = Text(content="", style=Style(text_style=TEXT_STYLE))
    rects = element_rects(Region(left=0, top=0, right=1, bottom=1), Region(left=2, top=0, right=4, bottom=4))
    painted = paint(text, {}, rects, text_lines("abcd", TEXT_STYLE), lines_are_solid=False)
    assert "".join(cell.grapheme for cell in painted.cells[:4]) == "  cd"


def test_text_beside_the_clip_draws_nothing() -> None:
    text = Text(content="", style=Style(text_style=TEXT_STYLE))
    rects = element_rects(Region(left=0, top=0, right=1, bottom=1), Region(left=3, top=0, right=4, bottom=4))
    painted = paint(text, {}, rects, text_lines("ab", TEXT_STYLE), lines_are_solid=False)
    assert painted.cells == Paint.blank(4, 4).cells


def test_a_gradient_margin_is_drawn_from_its_own_box_where_its_border_box_is_clipped_out() -> None:
    element = Div(style=Style(margin_color=DOWN))
    rects = boxes(BOX, Region(left=1, top=1, right=3, bottom=3), clip=Region(left=0, top=0, right=1, bottom=4))
    assert [row[0] for row in backgrounds(paint(element, {}, rects))] == [0, 85, 170, 255]


def test_a_gradient_element_without_a_margin_color_leaves_its_margin_alone() -> None:
    under = ("under", Div(style=Style(content_color=RED)), element_rects(BOX), (), True)
    over = ("over", FILLED, boxes(BOX, Region(left=1, top=1, right=3, bottom=3)), (), True)
    painted, _ = paint_layout([under, over], 4, 4, {})
    assert painted[0, 0].style.background == RED


def test_a_gradient_canvas_row_shorter_than_its_box_shows_the_canvas_background_past_it() -> None:
    canvas = Canvas(painter=Blank(), style=Style(content_color=RIGHT))
    lines = ((StyledGrapheme(grapheme="a"),),)
    painted = paint(canvas, {}, element_rects(Region(left=0, top=0, right=4, bottom=1)), lines)
    assert (backgrounds(painted)[0], painted[0, 0].grapheme) == ([0, 85, 170, 255], "a")


def test_gradient_text_that_moves_is_drawn_where_it_moved() -> None:
    fields: dict[str, NodeFields] = {}
    lines = text_lines("ab", TEXT_STYLE)
    paint(GRADIENT_TEXT, fields, element_rects(Region(left=0, top=0, right=2, bottom=1)), lines, False)
    moved = paint(GRADIENT_TEXT, fields, element_rects(Region(left=2, top=0, right=4, bottom=1)), lines, False)
    assert "".join(cell.grapheme for cell in moved.cells[:4]) == "  ab"
