from __future__ import annotations

from functools import lru_cache

from counterweight.geometry import Position
from counterweight.paint import Paint
from counterweight.styles.styles import JoinedBorderKind, JoinedBorderParts


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


def heal_borders(paint: Paint) -> Paint:
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
