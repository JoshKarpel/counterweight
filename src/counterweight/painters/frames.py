"""
Painters that draw what an app drew, such as a screenshot's frame or part of it,
which [`Paint.as_painter`][counterweight.paint.Paint.as_painter] makes.
"""

from __future__ import annotations

from dataclasses import dataclass

from counterweight.elements import Rows


@dataclass(frozen=True, slots=True)
class PaintView:
    """
    A [`Canvas`][counterweight.elements.Canvas] painter that draws a picture of cells taken from a paint,
    which [`Paint.as_painter`][counterweight.paint.Paint.as_painter] makes.
    Its natural size is the picture's, as an `<img>`'s is, and it doesn't scale, since cells can't,
    so rows and columns past the canvas's box are cut off, and the rest of a bigger box is left empty.
    """

    rows: Rows
    width: int
    """How many cells wide the picture is."""

    @property
    def natural_size(self) -> tuple[int, int]:
        return self.width, len(self.rows)

    @property
    def keeps_aspect_ratio(self) -> bool:
        return False

    def draw(self, width: int, height: int) -> Rows:
        """The picture's top `height` rows."""
        return self.rows[:height]
