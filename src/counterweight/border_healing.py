from __future__ import annotations

import logging
from functools import lru_cache

from more_itertools import flatten

from counterweight.geometry import Position
from counterweight.paint import BorderHealingHints, Cell, CellMap, Paint
from counterweight.styles.styles import JoinedBorderKind, JoinedBorderParts

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2**12)
def get_replacement_char(
    parts: JoinedBorderParts,
    center: str,
    left: str | None,
    right: str | None,
    above: str | None,
    below: str | None,
) -> str | None:
    if (
        c := parts.select(
            top=center in parts.connects_top or above in parts.connects_bottom,
            bottom=center in parts.connects_bottom or below in parts.connects_top,
            left=center in parts.connects_left or left in parts.connects_right,
            right=center in parts.connects_right or right in parts.connects_left,
        )
    ) != center:
        return c
    else:
        return None


@lru_cache(maxsize=2**12)
def dither(position: Position) -> tuple[Position, Position, Position, Position]:
    return (
        Position(position.x - 1, position.y),  # left
        Position(position.x + 1, position.y),  # right
        Position(position.x, position.y - 1),  # above
        Position(position.x, position.y + 1),  # below
    )


ALL_JOINED_BORDER_KIND_CHARS = set(flatten(k.value for k in JoinedBorderKind))


def heal_borders(paint: Paint, hints: BorderHealingHints) -> CellMap:
    overlay: CellMap = {}
    for center_position, parts in hints.items():
        center = paint.get(center_position)

        if center is None or center.grapheme not in ALL_JOINED_BORDER_KIND_CHARS:
            # Even if we got a hint, that cell may have been overwritten by another
            # element (e.g., putting a title over a border using absolute positioning).
            continue

        # Off-screen neighbors are None: a border running off the screen doesn't join borders that aren't drawn.
        # That's a decision (see run 12 in plans/performance-analysis-2026-03-07.md), not a constraint;
        # reversing it means keeping off-screen cells around for healing to look at.
        left, right, above, below = map(paint.get, dither(center_position))

        # TODO: cell styles and z-levels must match too (i.e., colors)

        if replaced_char := get_replacement_char(
            parts=parts,
            center=center.grapheme,
            left=left.grapheme if left else None,
            right=right.grapheme if right else None,
            above=above.grapheme if above else None,
            below=below.grapheme if below else None,
        ):
            overlay[center_position] = Cell(replaced_char, center.style)

    return overlay
