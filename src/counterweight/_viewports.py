"""
Where an app draws on its terminal, which `app` takes as its `viewport`:
the whole of the alternate screen, or a region below the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FullScreen:
    """
    Draw on the terminal's alternate screen, which the app fills, as a full-screen program like `vim` does,
    and hand the main screen back unchanged when the app stops.
    """

    mouse: bool = True
    """
    Whether to track the mouse, so the app receives mouse events.
    Tracking takes the mouse from the terminal, so turn it off to leave the terminal's own selection
    and scrolling to the user.
    """


@dataclass(frozen=True, slots=True)
class Inline:
    """
    Draw in a region below the prompt, as tall as the root's content, at most the terminal's height,
    with what the app prints above it, in the terminal's scrollback.

    The region's top row is the row the cursor is on when the app starts, from its first column,
    so it draws over the end of a line printed without a newline.
    The root is a flex item of a column as wide as the terminal, at most as tall as it,
    so a root taller than the terminal is cut off at the bottom, unless it can shrink, as on the web:
    keep content that grows in a [`scroll_area`][counterweight.widgets.scroll_area] that sticks to the end,
    and give the root `min_height(0)`, so the scroll area shrinks to fit and shows its newest lines.
    """

    keep_last_frame: bool = True
    """
    Whether to leave the region's last frame on the screen when the app stops, with the prompt below it,
    or to erase it, so the prompt comes back where the region started, as a picker whose result belongs on the
    next line does.
    """

    mouse: bool = False
    """
    Whether to track the mouse, so the app receives mouse events over its region.
    Tracking takes the wheel from the terminal, which is how a user scrolls back through what the app printed,
    so it's off by default.
    The terminal reports the mouse on the screen, not the region, so an app that tracks it asks the terminal where
    the cursor is (`CSI 6 n`) when it starts and after each resize, and works out where the region is in between.
    Mouse events above the region are over the terminal's scrollback, so the app drops them.
    """


type Viewport = FullScreen | Inline
