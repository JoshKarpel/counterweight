"""
How counterweight divides text into grapheme clusters and measures them,
for an app that cuts or pads text itself, whose cuts must match the ones layout and paint make.
"""

from counterweight._graphemes import grapheme_width
from counterweight._graphemes import graphemes
from counterweight._graphemes import visible

__all__ = [
    "grapheme_width",
    "graphemes",
    "visible",
]
