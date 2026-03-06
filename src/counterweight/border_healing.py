from __future__ import annotations

from functools import lru_cache

from more_itertools import flatten
from structlog import get_logger

from counterweight.geometry import Position
from counterweight.paint import BorderHealingHints, P, Paint
from counterweight.styles.styles import JoinedBorderKind, JoinedBorderParts

logger = get_logger()


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
        Position.flyweight(position.x - 1, position.y),  # left
        Position.flyweight(position.x + 1, position.y),  # right
        Position.flyweight(position.x, position.y - 1),  # above
        Position.flyweight(position.x, position.y + 1),  # below
    )


ALL_JOINED_BORDER_KIND_CHARS = set(flatten(k.value for k in JoinedBorderKind))


def heal_borders(paint: Paint, hints: BorderHealingHints) -> Paint:
    overlay: Paint = {}
    for center_position, parts in hints.items():
        center = paint[center_position]

        if center.char not in ALL_JOINED_BORDER_KIND_CHARS:
            # Even if we got a hint, that cell may have been overwritten by another
            # element (e.g., putting a title over a border using absolute positioning).
            continue

        left, right, above, below = map(paint.get, dither(center_position))

        # TODO: cell styles and z-levels must match too (i.e., colors)

        if replaced_char := get_replacement_char(
            parts=parts,
            center=center.char,
            left=left.char if left else None,
            right=right.char if right else None,
            above=above.char if above else None,
            below=below.char if below else None,
        ):
            overlay[center_position] = P(char=replaced_char, style=center.style, z=center.z)

    return overlay
