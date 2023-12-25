from __future__ import annotations

from functools import lru_cache
from typing import Literal, assert_never

from structlog import get_logger

from counterweight._utils import halve_integer
from counterweight.cell_paint import CellPaint, wrap_cells
from counterweight.components import AnyElement, Div, Text
from counterweight.geometry import Position
from counterweight.layout import BoxDimensions, Edge, LayoutBox, Rect
from counterweight.styles import Border
from counterweight.styles.styles import BorderEdge, CellStyle, JoinedBorderKind, JoinedBorderParts, Margin, Padding

logger = get_logger()

Paint = dict[Position, CellPaint]


def paint_layout(layout: LayoutBox) -> Paint:
    painted = paint_element(layout.element, layout.dims)
    for child in layout.children:
        painted |= paint_layout(child)  # no Z-level support! need something like a chainmap
    return painted


@lru_cache(maxsize=2**12)
def get_replacement_char(
    joined_border_parts: JoinedBorderParts,
    center: str,
    left: str | None,
    right: str | None,
    above: str | None,
    below: str | None,
) -> str | None:
    # we already know center must be SOME joined border part at this point

    v = joined_border_parts

    # TODO: this version is very compact but doesn't support either filling in gaps or cutting off bad runs, but that might be desirable...
    return v.select(
        top=center in v.connects_top or above in v.connects_bottom,
        bottom=center in v.connects_bottom or below in v.connects_top,
        left=center in v.connects_left or left in v.connects_right,
        right=center in v.connects_right or right in v.connects_left,
    )

    # left_connects_right = left in v.connects_right
    # right_connects_left = right in v.connects_left
    # above_connects_bottom = above in v.connects_bottom
    # below_connects_top = below in v.connects_top
    #
    # match left_connects_right, right_connects_left, above_connects_bottom, below_connects_top:
    #     case True, True, True, True:
    #         return v.horizontal_vertical
    #     case True, True, True, False:
    #         return v.horizontal_top
    #     case True, True, False, True:
    #         return v.horizontal_bottom
    #     case True, False, True, True:
    #         return v.vertical_left
    #     case False, True, True, True:
    #         return v.vertical_right
    #     case _:
    #         pass
    #
    # match center, left, right, above, below:
    #     # case _, l, r, a, b if l in v.connects_right and r in v.connects_left and a in v.connects_bottom and b in v.connects_top:
    #     #     return v.horizontal_vertical
    #     # case _, l, r, a, b if l in v.connects_right and r in v.connects_left and a not in v.connects_bottom and b in v.connects_top:
    #     #     return v.horizontal_bottom
    #     # case _, l, r, a, b if l in v.connects_right and r in v.connects_left and a in v.connects_bottom and b not in v.connects_top:
    #     #     return v.horizontal_top
    #     # case _, l, r, a, b if l not in v.connects_right and r in v.connects_left and a in v.connects_bottom and b in v.connects_top:
    #     #     return v.vertical_right
    #     # case _, l, r, a, b if l in v.connects_right and r not in v.connects_left and a in v.connects_bottom and b in v.connects_top:
    #     #     return v.vertical_left
    #     case c, l, r, _, _ if c in v.connects_bottom and c in v.connects_top and l in v.connects_right and r in v.connects_left:
    #         return v.horizontal_vertical
    #     case c, l, r, _, _ if c in v.connects_bottom and c in v.connects_top and l not in v.connects_right and r in v.connects_left:
    #         return v.vertical_right
    #     case c, l, r, _, _ if c in v.connects_bottom and c in v.connects_top and l in v.connects_right and r not in v.connects_left:
    #         return v.vertical_left
    #     case c, _, _, a, b if c in v.connects_left and c in v.connects_right and a in v.connects_bottom and b in v.connects_top:
    #         return v.horizontal_vertical
    #     case c, _, _, a, b if c in v.connects_left and c in v.connects_right and a not in v.connects_bottom and b in v.connects_top:
    #         return v.horizontal_bottom
    #     case c, _, _, a, b if c in v.connects_left and c in v.connects_right and a in v.connects_bottom and b not in v.connects_top:
    #         return v.horizontal_top
    #     # TODO: is there a way to keep the trick?
    #     # case _, _, v.horizontal, v.vertical, v.vertical:
    #     #     return v.vertical_right
    #     # case _, v.horizontal, _, v.vertical, v.vertical:
    #     #     return v.vertical_left
    #     # case _, v.horizontal, v.horizontal, _, v.vertical:
    #     #     return v.horizontal_bottom
    #     # case _, v.horizontal, v.horizontal, v.vertical, _:
    #     #     return v.horizontal_top
    #     # case v.right_bottom, _, v.horizontal, _, v.vertical:
    #     #     return v.horizontal_vertical
    #     # case v.right_bottom, _, _, _, v.vertical:
    #     #     return v.vertical_left
    #     # case v.right_bottom, _, v.horizontal, _, _:
    #     #     return v.horizontal_top
    #     # case v.vertical, _, v.horizontal, _, v.vertical:
    #     #     return v.vertical_right
    #     # case v.vertical, _, v.horizontal, _, None:
    #     #     return v.left_bottom
    #     # case v.horizontal, _, v.horizontal, _, v.vertical:
    #     #     return v.horizontal_bottom
    #     # case v.horizontal, _, None, _, v.vertical:
    #     #     return v.right_top
    #     # case v.vertical, _, v.horizontal, _, _:
    #     #     return v.vertical_right
    #     # case v.left_bottom, _, _, _, v.vertical:
    #     #     return v.vertical_right
    #     # case v.right_top, _, v.horizontal, _, _:
    #     #     return v.horizontal_bottom
    #     # TODO: there should be a more structured way to do this...
    #     case _:
    #         return None


def join_borders(paint: Paint) -> Paint:
    overlay: Paint = {}
    for p, cell_paint in paint.items():
        for tbk in JoinedBorderKind:
            v = tbk.value

            char = cell_paint.char
            if char not in v:  # the center character must be a joined border part
                continue

            left = paint.get(Position(p.x - 1, p.y))
            right = paint.get(Position(p.x + 1, p.y))
            above = paint.get(Position(p.x, p.y - 1))
            below = paint.get(Position(p.x, p.y + 1))

            # TODO: cell styles must match too (i.e., colors)

            if replaced_char := get_replacement_char(
                v,
                center=char,
                left=left.char if left else None,
                right=right.char if right else None,
                above=above.char if above else None,
                below=below.char if below else None,
            ):
                overlay[p] = cell_paint.model_copy(update={"char": replaced_char})

    return paint | overlay


def paint_element(element: AnyElement, dims: BoxDimensions) -> Paint:
    padding_rect, border_rect, margin_rect = dims.padding_border_margin_rects()
    m = paint_edge(element.style.margin, dims.margin, margin_rect)
    b = paint_border(element.style.border, border_rect) if element.style.border else {}
    t = paint_edge(element.style.padding, dims.padding, padding_rect)

    box = m | b | t

    match element:
        case Div():
            return box
        case Text() as e:
            return paint_text(e, dims.content) | box
        case _:
            raise NotImplementedError(f"Painting {element} is not implemented")


def justify_line(line: list[CellPaint], width: int, justify: Literal["left", "right", "center"]) -> list[CellPaint]:
    space = width - len(line)
    if space <= 0:
        return line
    elif justify == "left":
        return line + [CellPaint(char=" ")] * space
    elif justify == "right":
        return [CellPaint(char=" ")] * space + line
    elif justify == "center":
        left, right = halve_integer(space)
        return [CellPaint(char=" ")] * left + line + [CellPaint(char=" ")] * right
    else:
        assert_never(justify)


def paint_text(text: Text, rect: Rect) -> Paint:
    style = text.style.typography.style

    paint = {}
    lines = wrap_cells(
        cells=text.cells,
        wrap=text.style.typography.wrap,
        width=rect.width,
    )

    for y, line in enumerate(lines[: rect.height], start=rect.y):
        justified_line = justify_line(line, rect.width, text.style.typography.justify)
        for x, cell in enumerate(justified_line[: rect.width], start=rect.x):
            pos = Position(x, y)
            s = style | cell.style
            paint[pos] = CellPaint(char=cell.char, style=s)

    return paint


def paint_edge(mp: Margin | Padding, edge: Edge, rect: Rect, char: str = " ") -> Paint:
    cell_paint = CellPaint(char=char, style=CellStyle(background=mp.color))

    chars = {}

    # top
    for y in range(rect.top, rect.top + edge.top):
        for x in rect.x_range():
            chars[Position(x, y)] = cell_paint

    # bottom
    for y in range(rect.bottom, rect.bottom - edge.bottom, -1):
        for x in rect.x_range():
            chars[Position(x, y)] = cell_paint

    # left
    for x in range(rect.left, rect.left + edge.left):
        for y in rect.y_range():
            chars[Position(x, y)] = cell_paint

    # right
    for x in range(rect.right, rect.right - edge.right, -1):
        for y in rect.y_range():
            chars[Position(x, y)] = cell_paint

    return chars


def paint_border(border: Border, rect: Rect) -> Paint:
    style = border.style

    bv = border.kind.value
    left = bv.left
    right = bv.right
    top = bv.top
    bottom = bv.bottom
    left_top = bv.left_top
    right_top = bv.right_top
    left_bottom = bv.left_bottom
    right_bottom = bv.right_bottom

    contract = border.contract
    chars = {}

    rect_left = rect.left
    rect_top = rect.top
    rect_right = rect.right
    rect_bottom = rect.bottom

    draw_left = BorderEdge.Left in border.edges
    draw_right = BorderEdge.Right in border.edges
    draw_top = BorderEdge.Top in border.edges
    draw_bottom = BorderEdge.Bottom in border.edges

    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    v_slice = slice(contract_top, contract_bottom)
    h_slice = slice(contract_left, contract_right)

    if draw_left:
        left_paint = CellPaint(char=left, style=style)
        for p in rect.left_edge()[v_slice]:
            chars[p] = left_paint

    if draw_right:
        right_paint = CellPaint(char=right, style=style)
        for p in rect.right_edge()[v_slice]:
            chars[p] = right_paint

    if draw_top:
        top_paint = CellPaint(char=top, style=style)
        for p in rect.top_edge()[h_slice]:
            chars[p] = top_paint

    if draw_bottom:
        bottom_paint = CellPaint(char=bottom, style=style)
        for p in rect.bottom_edge()[h_slice]:
            chars[p] = bottom_paint

    if draw_top:
        if draw_left:
            chars[Position(x=rect_left, y=rect_top)] = CellPaint(char=left_top, style=style)
        if draw_right:
            chars[Position(x=rect_right, y=rect_top)] = CellPaint(char=right_top, style=style)

    if draw_bottom:
        if draw_left:
            chars[Position(x=rect_left, y=rect_bottom)] = CellPaint(char=left_bottom, style=style)
        if draw_right:
            chars[Position(x=rect_right, y=rect_bottom)] = CellPaint(char=right_bottom, style=style)

    return chars


def debug_paint(paint: dict[Position, CellPaint], rect: Rect) -> str:
    lines = []
    for y in rect.y_range():
        line = []
        for x in rect.x_range():
            line.append(paint.get(Position(x, y), CellPaint(char=" ")).char)

        lines.append(line)

    return "\n".join("".join(line) for line in lines)
