from __future__ import annotations

import logging
from collections.abc import Callable
from collections.abc import Hashable
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from dataclasses import replace
from functools import lru_cache
from itertools import groupby
from textwrap import dedent
from typing import Literal
from typing import assert_never
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement

import waxy

from counterweight._utils import flyweight
from counterweight._utils import halve_integer
from counterweight.elements import AnyElement
from counterweight.elements import Canvas
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.gradients import Box
from counterweight.gradients import Gradient
from counterweight.gradients import Indices
from counterweight.gradients import Ramp
from counterweight.gradients import field_indices
from counterweight.gradients import ramp
from counterweight.layout import Lines
from counterweight.layout import cells_width
from counterweight.layout import child_clip
from counterweight.layout import clipped_axes
from counterweight.styles.styles import CELL_STYLE_DEFAULTS
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import AnyColor
from counterweight.styles.styles import BorderKind
from counterweight.styles.styles import Color
from counterweight.styles.styles import JoinedBorderKind
from counterweight.styles.styles import JoinedBorderParts
from counterweight.styles.styles import ResolvedCellStyle
from counterweight.styles.styles import ResolvedStyle
from counterweight.styles.styles import Style
from counterweight.styles.styles import TextJustify
from counterweight.styles.styles import as_solid
from counterweight.styles.styles import is_solid
from counterweight.styles.styles import is_solid_cell_style
from counterweight.styles.styles import is_solid_color
from counterweight.styles.styles import resolve_cell_style
from counterweight.styles.styles import rgb_of
from counterweight.styles.styles import with_colors

logger = logging.getLogger(__name__)


@flyweight(maxsize=2**14)
@dataclass(frozen=True, slots=True)
class Cell:
    """
    What one terminal cell shows: a grapheme cluster and the resolved style it's drawn with.

    A cluster two cells wide is followed by a continuation cell, whose `grapheme` is empty,
    because the terminal draws the cluster across both.
    """

    grapheme: str
    style: ResolvedCellStyle[AnyColor]

    @classmethod
    @lru_cache(maxsize=2**10)
    def blank(cls, color: AnyColor) -> Cell:
        """A space on a `color` background."""
        return cls(" ", with_colors(CELL_STYLE_DEFAULTS, CELL_STYLE_DEFAULTS.foreground, color))

    @property
    def is_continuation(self) -> bool:
        """Whether this is the right half of a two-cell-wide cluster, which the cell to its left draws."""
        return not self.grapheme

    def erased(self) -> Cell:
        """
        A space in this cell's style, which is what a terminal leaves in the other half of a two-cell-wide
        cluster when one half is drawn over.
        """
        return Cell(" ", self.style)


BLANK = Cell.blank(color=Color.from_name("black"))


@dataclass(slots=True)
class Paint:
    """
    A screen's worth of cells, stored row by row.

    Index it with a `Position` or an `(x, y)` pair.
    Indexing outside the screen raises `IndexError` (negative coordinates don't wrap around),
    while [`get`][counterweight.paint.Paint.get] returns `None` there instead.

    Every two-cell-wide cluster is followed by its continuation cell on the same row, and every continuation
    cell follows one. Writing over one half of a pair erases the other half to a space, as a terminal does,
    so the cells written must not split a pair themselves (except where `write_row` clips them).
    """

    width: int
    height: int
    cells: list[Cell]

    @classmethod
    def blank(cls, width: int, height: int) -> Paint:
        """A `width` by `height` paint of [`BLANK`][counterweight.paint.BLANK] cells."""
        return cls(width, height, [BLANK] * (width * height))

    def index(self, x: int, y: int) -> int:
        """The offset of the cell at `(x, y)` in `cells`."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"({x}, {y}) is outside a {self.width}x{self.height} paint")
        return y * self.width + x

    def __getitem__(self, position: Position | tuple[int, int]) -> Cell:
        x, y = position if isinstance(position, tuple) else (position.x, position.y)
        return self.cells[self.index(x, y)]

    def __setitem__(self, position: Position | tuple[int, int], cell: Cell) -> None:
        x, y = position if isinstance(position, tuple) else (position.x, position.y)
        start = self.index(x, y)
        self._erase_split_pairs(start, start + 1)
        self.cells[start] = cell

    def _erase_split_pairs(self, start: int, stop: int) -> None:
        """
        Before `cells[start:stop]`, part of one row, are overwritten, erase the half outside them
        of any two-cell-wide cluster that straddles either end.
        """
        # A continuation cell never starts a row, so a pair split at either end lies within this row.
        cells = self.cells
        if (first := cells[start]).is_continuation:
            cells[start - 1] = first.erased()
        if stop < len(cells) and (after := cells[stop]).is_continuation:
            cells[stop] = after.erased()

    @property
    def bounds(self) -> Region:
        """The region the paint covers, which clips nothing when given as a clip."""
        return Region(left=0, top=0, right=self.width, bottom=self.height)

    def get(self, position: Position) -> Cell | None:
        """The cell at `position`, or `None` if it's off the screen."""
        if 0 <= position.x < self.width and 0 <= position.y < self.height:
            return self.cells[position.y * self.width + position.x]
        return None

    def fill(self, region: Region, cell: Cell, clip: Region) -> None:
        """Set every cell of `region` that is inside `clip` and on the screen to `cell`."""
        left, right = max(region.left, clip.left, 0), min(region.right, clip.right, self.width)
        if left >= right:
            return
        top, bottom = max(region.top, clip.top, 0), min(region.bottom, clip.bottom, self.height)
        w = self.width
        width = right - left
        row = [cell] * width
        cells = self.cells
        has_cells_after = right < w
        # _erase_split_pairs, inlined because every border and background fills row by row.
        for start in range(top * w + left, bottom * w + left, w):
            stop = start + width
            if not cells[start].grapheme:
                cells[start - 1] = cells[start].erased()
            if has_cells_after and not cells[stop].grapheme:
                cells[stop] = cells[stop].erased()
            cells[start:stop] = row

    def write_row(self, x: int, y: int, row: Sequence[Cell], clip: Region) -> None:
        """
        Set the cells from `(x, y)` rightward to `row`, dropping any that fall outside `clip` or off the screen,
        and erasing the half left inside of a two-cell-wide cluster that straddles their edge.
        """
        if not max(clip.top, 0) <= y < min(clip.bottom, self.height):
            return
        low = max(clip.left, 0)
        skip = low - x if x < low else 0
        keep = min(len(row), min(clip.right, self.width) - x)
        if skip >= keep:
            return
        start = y * self.width + x
        self._erase_split_pairs(start + skip, start + keep)
        if skip == 0 and keep == len(row):
            self.cells[start : start + keep] = row
            return
        visible = list(row[skip:keep])
        if visible[0].is_continuation:
            visible[0] = visible[0].erased()
        if keep < len(row) and row[keep].is_continuation:
            visible[-1] = visible[-1].erased()
        self.cells[start + skip : start + keep] = visible

    def rows(self) -> Iterator[list[Cell]]:
        """Each row of cells, top to bottom."""
        w = self.width
        return (self.cells[start : start + w] for start in range(0, w * self.height, w))

    def items(self) -> Iterator[tuple[Position, Cell]]:
        """Each cell with its position, row by row."""
        w = self.width
        return ((Position(i % w, i // w), cell) for i, cell in enumerate(self.cells))

    def copy(self) -> Paint:
        """A paint with the same cells, which changing this one doesn't affect."""
        return Paint(self.width, self.height, list(self.cells))


CellMap = dict[Position, Cell]
BorderHealingHints = dict[Position, JoinedBorderParts]
Fill = tuple[Region, Cell]
BorderSides = tuple[bool, bool, bool, bool]
Run = tuple[int, int, list[Cell]]  # cells to draw left to right from (x, y)
BorderPart = tuple[Region, str]
Corners = tuple[tuple[Position, JoinedBorderParts], ...]

DEFAULT_CELL_ASPECT_RATIO = 2.0
"""How many columns tall a row is, which is about right for most terminal fonts."""


def paint_layout[K: Hashable](
    elements: Iterable[tuple[K, AnyElement, Rects, Lines, bool]],
    width: int,
    height: int,
    fields: dict[K, NodeFields],
    cell_aspect_ratio: float = DEFAULT_CELL_ASPECT_RATIO,
) -> tuple[Paint, BorderHealingHints]:
    """
    Paint `elements` in the order given, which is paint order, so later elements are drawn over earlier ones.
    Each element comes with its key, its layout, its rows, and whether those rows' colors are all solid.

    An element with a gradient anywhere in its style or its rows is painted from the fields it keeps in `fields`
    by its key, which this replaces with the ones it used, so the next frame reuses those whose key hasn't changed.
    Its gradients compute in visual units, where a row is `cell_aspect_ratio` columns tall.
    """
    paint = Paint.blank(width, height)
    hints: BorderHealingHints = {}
    for key, element, resolved, lines, lines_are_solid in elements:
        style = element.style.resolved
        if is_solid(style) and lines_are_solid:
            hints.update(paint_element(paint, element, style, resolved, lines))
            continue
        node = fields.get(key)
        if node is None:
            node = fields[key] = NodeFields()
        hints.update(paint_gradient_element(paint, element, style, resolved, lines, node, cell_aspect_ratio))
    return paint, hints


def diff_paint(new: Paint, current: Paint) -> list[Run]:
    """
    The cells of `new` that differ from `current`, which must be the same size,
    as runs of adjacent changed cells, row by row.
    """
    if (new.width, new.height) != (current.width, current.height):
        raise ValueError(f"Can't diff a {new.width}x{new.height} paint against a {current.width}x{current.height} one")

    w = new.width
    runs: list[Run] = []
    for y, start in enumerate(range(0, w * new.height, w)):
        new_row = new.cells[start : start + w]
        current_row = current.cells[start : start + w]
        # Comparing whole rows runs in C and checks identity before equality, so unchanged rows are cheap to skip.
        if new_row == current_row:
            continue
        run_start = None
        for x, (new_cell, current_cell) in enumerate(zip(new_row, current_row, strict=True)):
            if new_cell is not current_cell and new_cell != current_cell:
                if run_start is None:
                    run_start = x
            elif run_start is not None:
                runs.append((run_start, y, new_row[run_start:x]))
                run_start = None
        if run_start is not None:
            runs.append((run_start, y, new_row[run_start:]))
    return runs


def runs_of(paint: Paint) -> list[Run]:
    """Every row of `paint` as one run, for drawing it in full."""
    return [(0, y, row) for y, row in enumerate(paint.rows())]


def text_rows(element: AnyElement, resolved: Rects, clip: Region, lines: Lines) -> tuple[range, Region]:
    """
    The rows of `lines` that are inside the clip, and the region that clips them:
    a `Canvas`'s content box, or for a `Text`, its own padding box on each axis its overflow clips.
    """
    if not lines:
        return range(0), clip
    if isinstance(element, Canvas):
        own_clip = clip.intersection(resolved.content)
    else:
        # Text overflows its box, as CSS's does, unless the Text's own overflow clips it to its padding box.
        own_clip = child_clip(clip, clip, resolved, "padding", *clipped_axes(element.style))
    if own_clip is None:
        return range(0), clip
    content = resolved.content
    return range(max(own_clip.top, content.top), min(own_clip.bottom, content.top + len(lines))), own_clip


def paint_element(
    paint: Paint, element: AnyElement, style: ResolvedStyle[AnyColor], resolved: Rects, lines: Lines
) -> Corners:
    """
    Paint the part of one element inside its clip onto `paint`,
    returning the border healing hints for its corners inside the clip.

    `lines` are the rows a `Text` wraps to, which layout wrapped it to, or the rows a `Canvas`'s painter drew,
    and are empty for a `Div`.
    Only the rows inside the clip are built, so a long text in a scroll container costs only the rows in view,
    and an element paints nothing if its border box, its text and any `margin_color` margin all miss the clip.
    Text overflows its box down and to the right, so the border box alone can't decide that.
    A canvas's rows never leave its content box, which clips them.

    The margin edge, border, padding edge and text each cover different cells,
    so only the background fill underneath them has to come first.
    The background fills the border box, and the margin is painted only where the element's own style
    sets `margin_color`, so a margin leaves whatever lies beneath it visible, as on the web.
    An element with no border, padding, text, `margin_color` or `content_color` paints nothing,
    not even its background, so an undecorated container laid over other elements leaves them visible.

    A hint for a corner outside the clip is dropped, because healing only checks that the cell under a hint
    is a border character, so it would rewrite whatever border was drawn there instead.
    """
    clip = resolved.clip
    if clip is None:
        return ()

    rows, text_clip = text_rows(element, resolved, clip, lines)
    has_margin_color = element.style.margin_color is not UNSET
    if (
        resolved.visible is None
        and not rows
        and not (has_margin_color and resolved.margin.intersection(clip) is not None)
    ):
        return ()

    border, corners = border_fills(
        style.border_kind,
        style.border_style,
        style.border_contract,
        resolved.border,
        border_sides(element.style),
    )
    hints = visible_corners(corners, resolved, clip)
    margin = edge_fills(resolved.margin, resolved.border, style.margin_color) if has_margin_color else ()
    fills = margin + border + edge_fills(resolved.padding, resolved.content, style.padding_color)

    if not fills and not lines and element.style.content_color is UNSET:
        return hints

    paint.fill(resolved.border, Cell.blank(color=style.content_color), clip)
    for region, cell in fills:
        paint.fill(region, cell, clip)
    if isinstance(element, Canvas):
        text_justify: TextJustify = "left"
        text_style = as_solid(canvas_text_style(element.style))
    else:
        text_justify = style.text_justify
        text_style = style.text_style
    content = resolved.content
    for y in rows:
        paint.write_row(
            content.left,
            y,
            line_cells(lines[y - content.top], text_justify, text_style, content.width),
            text_clip,
        )

    return hints


def visible_corners(corners: Corners, resolved: Rects, clip: Region) -> Corners:
    """The border healing hints of the `corners` inside the clip."""
    # A border box wholly inside the clip is its own visible part, so all of its corners are too.
    if resolved.visible is resolved.border:
        return corners
    return tuple((position, parts) for position, parts in corners if clip.contains(position))


@dataclass(frozen=True, slots=True, eq=False)
class Field:
    """
    The ramp entry of each cell of some strips of the screen, for one gradient mapped over a box of `size`,
    at a cell aspect ratio of `aspect`, with the strips relative to the box's top left cell.
    """

    size: tuple[int, int]
    aspect: float
    strips: tuple[Region, ...]
    indices: tuple[Indices, ...]


type Slot = Literal["margin", "content", "padding", "border", "text"]


@dataclass(slots=True)
class NodeFields:
    """
    What paint built for one node's gradients, kept across frames by node (see `LayoutTree.fields`):
    the fields of each slot's gradients, and the cells each slot drew, with what they were drawn from.
    A frame reuses each one whose inputs are unchanged, and keeps only the fields it used.
    """

    fields: dict[tuple[Slot, Gradient], Field] = dataclass_field(default_factory=dict)
    painted: dict[Slot, tuple[object, tuple[Run, ...], dict[tuple[Slot, Gradient], Field]]] = dataclass_field(
        default_factory=dict
    )


@dataclass(slots=True)
class GradientSlots:
    """Builds, or reuses from the last frame, the fields and cells of one element's gradients in one frame."""

    resolved: Rects
    aspect: float
    area: Region
    node: NodeFields
    used: dict[tuple[Slot, Gradient], Field] = dataclass_field(default_factory=dict)

    def field(self, slot: Slot, gradient: Gradient, default_box: Box, strips: tuple[Region, ...]) -> Field:
        """The field of `gradient` over `strips` of the screen, mapped over its box, or `default_box` if it names none."""
        box = box_of(self.resolved, gradient.box or default_box)
        size = (box.width, box.height)
        relative = tuple(
            Region(
                left=strip.left - box.left,
                top=strip.top - box.top,
                right=strip.right - box.left,
                bottom=strip.bottom - box.top,
            )
            for strip in strips
        )
        key = (slot, gradient)
        built = self.used.get(key) or self.node.fields.get(key)
        if built is None or built.size != size or built.aspect != self.aspect or built.strips != relative:
            built = Field(
                size=size,
                aspect=self.aspect,
                strips=relative,
                indices=tuple(field_indices(gradient, box.width, box.height, self.aspect, strip) for strip in relative),
            )
        self.used[key] = built
        return built

    def painted(self, slot: Slot, inputs: object, draw: Callable[[], tuple[Run, ...]]) -> tuple[Run, ...]:
        """
        The runs `slot` draws from `inputs`: those it drew last frame if they were drawn from equal inputs,
        keeping the fields they were drawn from, or `draw`'s.
        """
        previous = self.node.painted.get(slot)
        if previous is not None and previous[0] == inputs:
            self.used.update(previous[2])
            return previous[1]
        before = set(self.used)
        runs = draw()
        self.node.painted[slot] = (inputs, runs, {key: field for key, field in self.used.items() if key not in before})
        return runs

    def background(self, slot: Slot, color: Gradient, default_box: Box, regions: Iterable[Region]) -> tuple[Run, ...]:
        """The runs of blank cells that fill the parts of `regions` inside the clip with `color`'s gradient."""
        strips = self.visible(regions)

        def draw() -> tuple[Run, ...]:
            cells = _BlankCells(ramp(color))
            field = self.field(slot, color, default_box, strips)
            return tuple(
                (strip.left, strip.top + dy, list(map(cells.__getitem__, row)))
                for strip, indices in zip(strips, field.indices, strict=True)
                for dy, row in enumerate(indices)
            )

        return self.painted(slot, (color, strips, box_of(self.resolved, color.box or default_box), self.aspect), draw)

    def border(self, parts: tuple[BorderPart, ...], style: ResolvedCellStyle[AnyColor | Gradient]) -> tuple[Run, ...]:
        """The runs of a border's `parts` inside the clip, in the order they overwrite each other, drawn in `style`."""
        visible = [
            (strip, character) for region, character in parts if (strip := self.area.intersection(region)) is not None
        ]
        strips = tuple(strip for strip, _ in visible)

        def draw() -> tuple[Run, ...]:
            foreground = self.colors(style.foreground, "border", "border", strips)
            background = self.colors(style.background, "border", "border", strips)
            return tuple(
                (
                    strip.left,
                    strip.top + dy,
                    [
                        Cell(character, with_colors(style, foreground(index, dy, dx), background(index, dy, dx)))
                        for dx in range(strip.width)
                    ],
                )
                for index, (strip, character) in enumerate(visible)
                for dy in range(strip.height)
            )

        boxes = (self.resolved.border, self.resolved.padding, self.resolved.content, self.resolved.margin)
        return self.painted("border", (parts, style, strips, boxes, self.aspect), draw)

    def colors(
        self, color: AnyColor | Gradient, slot: Slot, default_box: Box, strips: tuple[Region, ...]
    ) -> Callable[[int, int, int], AnyColor]:
        """The color of the cell `dx` across and `dy` down strip `index` of `strips`, from `color`."""
        if is_solid_color(color):
            return lambda index, dy, dx: color
        field = self.field(slot, color, default_box, strips)
        color_of = ramp(color).color
        return lambda index, dy, dx: color_of(field.indices[index][dy][dx])

    def visible(self, regions: Iterable[Region]) -> tuple[Region, ...]:
        """The non-empty parts of `regions` inside the clip and on the screen."""
        return tuple(strip for region in regions if (strip := self.area.intersection(region)) is not None)


class _BlankCells(dict[int, Cell]):
    """The blank cell of each ramp entry met so far, so a field's cells look each entry's color up once."""

    __slots__ = ("ramp",)

    def __init__(self, gradient_ramp: Ramp) -> None:
        super().__init__()
        self.ramp = gradient_ramp

    def __missing__(self, index: int) -> Cell:
        cell = self[index] = Cell.blank(self.ramp.color(index))
        return cell


def box_of(resolved: Rects, box: Box) -> Region:
    """The region of one of an element's boxes."""
    match box:
        case "margin":
            return resolved.margin
        case "border":
            return resolved.border
        case "padding":
            return resolved.padding
        case "content":
            return resolved.content
        case _ as unreachable:
            assert_never(unreachable)


def paint_gradient_element(
    paint: Paint,
    element: AnyElement,
    style: ResolvedStyle[AnyColor | Gradient],
    resolved: Rects,
    lines: Lines,
    node: NodeFields,
    aspect: float,
) -> Corners:
    """
    Paint one element as `paint_element` does, for an element with a gradient in its style or its rows:
    each slot that holds a solid color fills as it does there, and each that holds a gradient paints from its field.
    The fields and cells it builds are kept in `node`, and the next frame reuses those whose inputs are unchanged.
    """
    clip = resolved.clip
    if clip is None:
        return ()
    area = clip.intersection(paint.bounds)
    if area is None:
        return ()

    rows, text_clip = text_rows(element, resolved, clip, lines)
    has_margin_color = element.style.margin_color is not UNSET
    if (
        resolved.visible is None
        and not rows
        and not (has_margin_color and resolved.margin.intersection(clip) is not None)
    ):
        return ()

    parts, corners = border_parts(
        style.border_kind, style.border_contract, resolved.border, border_sides(element.style)
    )
    hints = visible_corners(corners, resolved, clip)
    margin = edge_strips(resolved.margin, resolved.border) if has_margin_color else ()
    padding = edge_strips(resolved.padding, resolved.content)

    if not (margin or parts or padding) and not lines and element.style.content_color is UNSET:
        return hints

    slots = GradientSlots(resolved=resolved, aspect=aspect, area=area, node=node)
    background_fill(paint, slots, "content", style.content_color, "border", (resolved.border,), clip)
    background_fill(paint, slots, "margin", style.margin_color, "margin", margin, clip)
    if is_solid_cell_style(style.border_style):
        for region, character in parts:
            paint.fill(region, Cell(character, style.border_style), clip)
    else:
        write_runs(paint, slots.border(parts, style.border_style), clip)
    background_fill(paint, slots, "padding", style.padding_color, "padding", padding, clip)

    if rows:
        if isinstance(element, Canvas):
            text_justify: TextJustify = "left"
            text_style = canvas_text_style(element.style)
        else:
            text_justify = style.text_justify
            text_style = style.text_style
        write_runs(paint, gradient_text(slots, lines, rows, text_clip, text_justify, text_style), text_clip)

    node.fields = slots.used
    return hints


def background_fill(
    paint: Paint,
    slots: GradientSlots,
    slot: Slot,
    color: AnyColor | Gradient,
    default_box: Box,
    regions: tuple[Region, ...],
    clip: Region,
) -> None:
    """Fill `regions` inside the clip with blank cells of `color`, which, if it's a gradient, maps over its box."""
    if not regions:
        return
    if is_solid_color(color):
        cell = Cell.blank(color)
        for region in regions:
            paint.fill(region, cell, clip)
        return
    write_runs(paint, slots.background(slot, color, default_box, regions), clip)


def write_runs(paint: Paint, runs: Iterable[Run], clip: Region) -> None:
    for x, y, cells in runs:
        paint.write_row(x, y, cells, clip)


def gradient_text(
    slots: GradientSlots,
    lines: Lines,
    rows: range,
    text_clip: Region,
    justify: TextJustify,
    text_style: ResolvedCellStyle[AnyColor | Gradient],
) -> tuple[Run, ...]:
    """
    The runs of the `rows` of text inside the clip, from `lines`, where any grapheme whose style holds a gradient
    takes its color from the gradient's field at its first cell inside the clip, and keeps it across both cells
    if it's two wide, since the terminal draws both halves in one style.
    A grapheme's own color, from its chunk, wins over the text style's, as in `line_cells`.
    """
    content = slots.resolved.content

    def draw() -> tuple[Run, ...]:
        justified = [justify_line(list(lines[y - content.top]), content.width, justify) for y in rows]
        longest = max(cells_width(line) for line in justified)
        extent = Region(left=content.left, top=rows.start, right=content.left + longest, bottom=rows.stop)
        on_screen = slots.area.intersection(extent)
        region = None if on_screen is None else on_screen.intersection(text_clip)
        colors: dict[AnyColor | Gradient, Callable[[int, int, int], AnyColor]] = {}

        def color_at(color: AnyColor | Gradient, x: int, y: int) -> AnyColor:
            if region is None or not (region.left <= x < region.right):
                return _UNSEEN
            colors_of = colors.get(color)
            if colors_of is None:
                colors_of = colors[color] = slots.colors(color, "text", "content", (region,))
            return colors_of(0, y - region.top, x - region.left)

        runs = []
        for y, line in zip(rows, justified, strict=True):
            cells: list[Cell] = []
            x = content.left
            previous_style = None
            for styled in line:
                if not styled.width:
                    continue
                if styled.style is not previous_style:
                    resolved_style = resolve_cell_style(styled.style, text_style)
                    previous_style = styled.style
                if is_solid_cell_style(resolved_style):
                    cell_style = resolved_style
                else:
                    # The first of the cluster's cells inside the clip, so a cluster cut off on the left matches the field.
                    sample = x if region is None else max(x, region.left)
                    cell_style = with_colors(
                        resolved_style,
                        color_at(resolved_style.foreground, sample, y),
                        color_at(resolved_style.background, sample, y),
                    )
                cells.append(Cell(styled.grapheme, cell_style))
                if styled.width == 2:
                    cells.append(Cell("", cell_style))
                x += styled.width
            runs.append((content.left, y, cells))
        return tuple(runs)

    boxes = (slots.resolved.border, slots.resolved.padding, content, slots.resolved.margin)
    return slots.painted("text", (lines, rows, text_clip, slots.area, justify, text_style, boxes, slots.aspect), draw)


_UNSEEN = Color(0, 0, 0)
"""The color of the part of a gradient a cell outside the clip would take, which is never drawn."""


@lru_cache(maxsize=2**8)
def canvas_text_style(style: Style) -> ResolvedCellStyle[AnyColor | Gradient]:
    """
    The style a `Canvas` with `style` resolves its painter's cells against:
    its `text_style`, whose background is its `content_color` unless the `text_style` sets one.
    A `content_color` gradient maps over the border box there too, unless it names its own box,
    so the cells the painter leaves transparent match the rest of the box.
    """
    resolved = style.resolved
    if style.text_style.background is not UNSET:
        return resolved.text_style
    background = resolved.content_color
    if not is_solid_color(background) and background.box is None:
        background = replace(background, box="border")
    return with_colors(resolved.text_style, resolved.text_style.foreground, background)


@lru_cache(maxsize=2**12)
def edge_strips(outer: Region, inner: Region) -> tuple[Region, ...]:
    """The parts of `outer` outside `inner`, as up to four strips."""
    strips = (
        Region(left=outer.left, top=outer.top, right=outer.right, bottom=inner.top),
        Region(left=outer.left, top=inner.bottom, right=outer.right, bottom=outer.bottom),
        Region(left=outer.left, top=inner.top, right=inner.left, bottom=inner.bottom),
        Region(left=inner.right, top=inner.top, right=outer.right, bottom=inner.bottom),
    )
    return tuple(strip for strip in strips if not strip.is_empty)


@lru_cache(maxsize=2**12)
def edge_fills(outer: Region, inner: Region, color: AnyColor) -> tuple[Fill, ...]:
    """The parts of `outer` outside `inner`, as up to four strips filled with blank cells of `color`."""
    cell = Cell.blank(color=color)
    return tuple((strip, cell) for strip in edge_strips(outer, inner))


def justify_line(line: list[StyledGrapheme], width: int, justify: TextJustify) -> list[StyledGrapheme]:
    space = width - cells_width(line)
    if space <= 0:
        return line
    if justify == "left":
        return line + [StyledGrapheme(grapheme=" ")] * space
    if justify == "right":
        return [StyledGrapheme(grapheme=" ")] * space + line
    if justify == "center":
        left, right = halve_integer(space)
        return [StyledGrapheme(grapheme=" ")] * left + line + [StyledGrapheme(grapheme=" ")] * right
    assert_never(justify)


@lru_cache(maxsize=2**12)
def line_cells(
    line: tuple[StyledGrapheme, ...], justify: TextJustify, text_style: ResolvedCellStyle[AnyColor], width: int
) -> tuple[Cell, ...]:
    """
    The cells one wrapped row of text fills when justified at `width`, at least `width` cells long.
    A zero-width cluster takes no cell, so it isn't drawn.
    Every grapheme's style must be solid, as a gradient's colors depend on where its cells are.
    """
    cells: list[Cell] = []
    previous_style = None
    for styled in justify_line(list(line), width, justify):
        if not styled.width:
            continue
        if styled.style is not previous_style:
            resolved_style = as_solid(resolve_cell_style(styled.style, text_style))
            previous_style = styled.style
        cells.append(Cell(styled.grapheme, resolved_style))
        if styled.width == 2:
            cells.append(Cell("", resolved_style))
    return tuple(cells)


_ONE_CELL = waxy.Length(1)


@lru_cache(maxsize=2**12)
def border_sides(style: Style) -> BorderSides:
    """
    Which sides of the border an element with `style` draws, left, right, top and bottom:
    those whose width is one cell.
    They come from the style rather than from the gap between the border and padding boxes,
    because a scroll container's `scrollbar_width` widens that gap without drawing anything in it.
    """
    layout = style.layout
    return (
        layout.border_left == _ONE_CELL,
        layout.border_right == _ONE_CELL,
        layout.border_top == _ONE_CELL,
        layout.border_bottom == _ONE_CELL,
    )


@lru_cache(maxsize=2**12)
def border_fills(
    kind: BorderKind | None,
    cell_style: ResolvedCellStyle[AnyColor],
    contract: int,
    region: Region,
    sides: BorderSides,
) -> tuple[tuple[Fill, ...], Corners]:
    """
    A border's edges and corners as one-cell-wide fills of cells in `cell_style`, as `border_parts` gives them,
    and the corners that border healing may join to a neighboring border.
    """
    parts, corners = border_parts(kind, contract, region, sides)
    return tuple((part, Cell(character, cell_style)) for part, character in parts), corners


@lru_cache(maxsize=2**12)
def border_parts(
    kind: BorderKind | None,
    contract: int,
    region: Region,
    sides: BorderSides,
) -> tuple[tuple[BorderPart, ...], Corners]:
    """
    A border's edges and corners as one-cell-wide regions and the character each is drawn with,
    in the order they overwrite each other, and the corners that border healing may join to a neighboring border.

    The border runs around the edge of the border box `region`, on the `sides` (left, right, top and bottom) it's drawn on.
    """
    if kind is None:
        return (), ()

    bv = kind.value

    draw_left, draw_right, draw_top, draw_bottom = sides

    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    rows = range(region.top, region.bottom)[contract_top:contract_bottom] if not region.is_empty else range(0)
    columns = range(region.left, region.right)[contract_left:contract_right] if not region.is_empty else range(0)

    def column(x: int) -> Region:
        return Region(left=x, top=rows.start, right=x + 1, bottom=rows.start + len(rows))

    def row(y: int) -> Region:
        return Region(left=columns.start, top=y, right=columns.start + len(columns), bottom=y + 1)

    def point(position: Position) -> Region:
        return Region(left=position.x, top=position.y, right=position.x + 1, bottom=position.y + 1)

    parts: list[BorderPart] = []
    if draw_left and rows:
        parts.append((column(region.left), bv.left))
    if draw_right and rows:
        parts.append((column(region.right - 1), bv.right))
    if draw_top:
        if columns:
            parts.append((row(region.top), bv.top))
        if draw_left:
            parts.append((point(region.top_left), bv.left_top))
        if draw_right:
            parts.append((point(region.top_right), bv.right_top))
    if draw_bottom:
        if columns:
            parts.append((row(region.bottom - 1), bv.bottom))
        if draw_left:
            parts.append((point(region.bottom_left), bv.left_bottom))
        if draw_right:
            parts.append((point(region.bottom_right), bv.right_bottom))

    try:
        jbv = JoinedBorderKind[kind.name].value
    except KeyError:
        return tuple(parts), ()

    corners = []
    if draw_top:
        if draw_left:
            corners.append(region.top_left)
        if draw_right:
            corners.append(region.top_right)
    if draw_bottom:
        if draw_left:
            corners.append(region.bottom_left)
        if draw_right:
            corners.append(region.bottom_right)

    return tuple(parts), tuple((corner, jbv) for corner in corners)


SVG_FOREGROUND = Color.from_name("white")
SVG_BACKGROUND = Color.from_name("black")
"""What `svg` draws the terminal's default foreground and background in."""


def svg(paint: Paint) -> Element:
    w, h = paint.width, paint.height

    x_mul = 0.55  # x coordinates get cut roughly in half because monospace cells are twice as tall as they are wide
    y_mul = 1.13  # seems to make border connect up just right

    fmt = "0.2f"
    unit = "em"

    root = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{w * x_mul:{fmt}}{unit}",
            "height": f"{h * y_mul:{fmt}}{unit}",
        },
    )

    style = SubElement(
        root,
        "style",
        {},
    )
    style.text = dedent(
        """\
        svg {
          dominant-baseline: hanging;
          font-size: 1rem;
        }
        """
    )

    background_root = SubElement(
        root,
        "g",
        {
            "shape-rendering": "crispEdges",
        },
    )
    SubElement(  # default background color is black, so do a single black rectangle to cover the whole background as an optimization
        background_root,
        "rect",
        {
            "x": f"{0 * x_mul:{fmt}}{unit}",
            "y": f"{0 * y_mul:{fmt}}{unit}",
            "width": f"{w * x_mul:{fmt}}{unit}",
            "height": f"{h * y_mul:{fmt}}{unit}",
            "fill": SVG_BACKGROUND.hex,
        },
    )

    text_root = SubElement(
        root,
        "text",
        {
            "fill": SVG_FOREGROUND.hex,
            "font-family": "monospace",
        },
    )

    for y, row in enumerate(paint.rows()):
        cells = list(enumerate(row))
        row_tspan_root = SubElement(
            text_root,
            "tspan",
            {
                "y": f"{y * y_mul:{fmt}}{unit}",
            },
        )

        for bg_color, x_cells_group in groupby(
            cells, key=lambda x_cell: rgb_of(x_cell[1].style.background, SVG_BACKGROUND).hex
        ):
            # Optimization: write out long horizontal rectangles of the same background color as rectangles instead of individual cell-sized rectangles
            x_cells = tuple(x_cells_group)
            first_x, _first_cell = x_cells[0]

            SubElement(
                background_root,
                "rect",
                {
                    "x": f"{first_x * x_mul:{fmt}}{unit}",
                    "y": f"{y * y_mul:{fmt}}{unit}",
                    "width": f"{len(x_cells) * x_mul:{fmt}}{unit}",
                    "height": f"{1 * y_mul:{fmt}}{unit}",
                    "fill": bg_color,
                },
            )

            for x, cell in x_cells:
                # optimization: don't write spaces; continuation cells are drawn by the cluster to their left
                if cell.grapheme == " " or cell.is_continuation:
                    continue

                ts = SubElement(
                    row_tspan_root,
                    "tspan",
                    {
                        "x": f"{x * x_mul:{fmt}}{unit}",
                    },
                )

                # optimization: don't write the default foreground
                if (foreground := rgb_of(cell.style.foreground, SVG_FOREGROUND)) != SVG_FOREGROUND:
                    ts.attrib["fill"] = foreground.hex
                ts.attrib.update(svg_text_style(cell.style))
                ts.text = cell.grapheme

    return root


def svg_text_style(style: ResolvedCellStyle[AnyColor]) -> dict[str, str]:
    """The SVG attributes that draw a cell's bold, dim, italic, underline, and strikethrough, which are off by default."""
    attributes = {}
    if style.bold:
        attributes["font-weight"] = "bold"
    if style.dim:
        attributes["fill-opacity"] = "0.5"
    if style.italic:
        attributes["font-style"] = "italic"
    if decorations := " ".join(
        decoration
        for decoration, is_on in (("underline", style.underline), ("line-through", style.strikethrough))
        if is_on
    ):
        attributes["text-decoration"] = decorations
    return attributes
