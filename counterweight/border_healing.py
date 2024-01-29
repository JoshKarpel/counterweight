from __future__ import annotations

from functools import lru_cache

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


def heal_borders(paint: Paint) -> Paint:
    overlay: Paint = {}
    for pos, p in paint.items():
        char = p.char
        for kind in JOINED_BORDER_KINDS:
            if char not in kind:  # the center character must be a joined border part
                continue

            left, right, above, below = map(paint.get, dither(pos))

            # TODO: cell styles and z-levels must match too (i.e., colors)

            if replaced_char := get_replacement_char(
                kind,
                center=char,
                left=left.char if left else None,
                right=right.char if right else None,
                above=above.char if above else None,
                below=below.char if below else None,
            ):
                overlay[pos] = P(char=replaced_char, style=p.style, z=p.z)

    return overlay
