"""
What an app draws, cell by cell: the [`Paint`][counterweight.paint.Paint] a
[`Painter`][counterweight.elements.Painter] returns for a [`Canvas`][counterweight.elements.Canvas],
and the [`Frame`][counterweight.paint.Frame] a [`Screenshot`][counterweight.controls.Screenshot] captures.
"""

from counterweight._output import Frame
from counterweight._paint import BLANK
from counterweight._paint import SCREENSHOT_BACKGROUND
from counterweight._paint import SCREENSHOT_FOREGROUND
from counterweight._paint import Cell
from counterweight._paint import Paint
from counterweight._paint import rows_of
from counterweight._paint import styled_grapheme

__all__ = [
    "BLANK",
    "SCREENSHOT_BACKGROUND",
    "SCREENSHOT_FOREGROUND",
    "Cell",
    "Frame",
    "Paint",
    "rows_of",
    "styled_grapheme",
]
