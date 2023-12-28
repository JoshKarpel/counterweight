from __future__ import annotations

from functools import lru_cache

from counterweight.cell_paint import CellPaint
from counterweight.geometry import Position
from counterweight.paint import Paint
from counterweight.styles.styles import JoinedBorderKind, JoinedBorderParts


@lru_cache(maxsize=2**12)
def get_replacement_char(
    parts: JoinedBorderParts,
    center: str,
    left: str | None,
    right: str | None,
    above: str | None,
    below: str | None,
) -> str | None:
    return parts.select(
        top=center in parts.connects_top or above in parts.connects_bottom,
        bottom=center in parts.connects_bottom or below in parts.connects_top,
        left=center in parts.connects_left or left in parts.connects_right,
        right=center in parts.connects_right or right in parts.connects_left,
    )


@lru_cache(maxsize=2**12)
def dither(position: Position) -> tuple[Position, Position, Position, Position]:
    return (
        Position(position.x - 1, position.y),  # left
        Position(position.x + 1, position.y),  # right
        Position(position.x, position.y - 1),  # above
        Position(position.x, position.y + 1),  # below
    )


JOINED_BORDER_KINDS = tuple(k.value for k in JoinedBorderKind)


def heal_borders(paint: Paint) -> Paint:
    overlay: Paint = {}
    for p, cell_paint in paint.items():
        char = cell_paint.char
        for kind in JOINED_BORDER_KINDS:
            if char not in kind:  # the center character must be a joined border part
                continue

            left, right, above, below = map(paint.get, dither(p))

            # TODO: cell styles must match too (i.e., colors)

            if replaced_char := get_replacement_char(
                kind,
                center=char,
                left=left.char if left else None,
                right=right.char if right else None,
                above=above.char if above else None,
                below=below.char if below else None,
            ):
                overlay[p] = CellPaint(char=replaced_char, style=cell_paint.style)

    return overlay
