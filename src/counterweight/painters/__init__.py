"""
Painters that draw a [`Canvas`][counterweight.elements.Canvas]'s content box:
pictures made of pixels ([`Pixels`][counterweight.painters.Pixels] and [`HalfBlocks`][counterweight.painters.HalfBlocks]),
what a terminal emulator shows ([`ScreenView`][counterweight.painters.ScreenView]
and [`Transcript`][counterweight.painters.Transcript]),
and what an app drew ([`PaintView`][counterweight.painters.PaintView]).
"""

from counterweight.painters._frames import PaintView
from counterweight.painters._pixels import Fit
from counterweight.painters._pixels import HalfBlockGradient
from counterweight.painters._pixels import HalfBlocks
from counterweight.painters._pixels import Pixels
from counterweight.painters._pixels import SupportsRGBA
from counterweight.painters._terminal import MAX_LINES
from counterweight.painters._terminal import ScreenView
from counterweight.painters._terminal import Transcript

__all__ = [
    "MAX_LINES",
    "Fit",
    "HalfBlockGradient",
    "HalfBlocks",
    "PaintView",
    "Pixels",
    "ScreenView",
    "SupportsRGBA",
    "Transcript",
]
