from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from more_itertools import flatten

from counterweight.geometry import Position
from counterweight.paint import P, Paint
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
        Position.flyweight(position.x - 1, position.y),  # left
        Position.flyweight(position.x + 1, position.y),  # right
        Position.flyweight(position.x, position.y - 1),  # above
        Position.flyweight(position.x, position.y + 1),  # below
    )


JOINED_BORDER_KINDS = tuple(k.value for k in JoinedBorderKind)
ALL_JOINED_BORDER_CHARS = set(flatten(JOINED_BORDER_KINDS))


def heal_borders(paint: Paint, hints: Iterable[Position]) -> Paint:
    overlay: Paint = {}
    for center_position in hints:
        center = paint[center_position]
        left, right, above, below = map(paint.get, dither(center_position))

        if center.char not in ALL_JOINED_BORDER_CHARS:  # the center character must be a joined border part
            continue

        for kind in JOINED_BORDER_KINDS:
            # TODO: cell styles and z-levels must match too (i.e., colors)

            # TODO: Should hints include original border type to avoid iterating, and to not overwrite here multiple times?
            if replaced_char := get_replacement_char(
                kind,
                center=center.char,
                left=left.char if left else None,
                right=right.char if right else None,
                above=above.char if above else None,
                below=below.char if below else None,
            ):
                overlay[center_position] = P(char=replaced_char, style=center.style, z=center.z)
                break

    return overlay
