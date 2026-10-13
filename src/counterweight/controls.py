from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TextIO, Union

from counterweight.focus import ElementHandle, FocusHandle, Subtree
from counterweight.geometry import Position

if TYPE_CHECKING:
    from counterweight.output import Frame


@dataclass(frozen=True, slots=True)
class _Control:
    pass


@dataclass(frozen=True, slots=True)
class Quit(_Control):
    """
    Cause the application to quit.

    The quit occurs at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the application exits.
    """


@dataclass(frozen=True, slots=True)
class Bell(_Control):
    """
    Cause the terminal to emit a bell sound.

    The bell occurs at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the sound is played.
    """


# How Screenshot.to_file encodes a frame, by the suffix of the path it writes to.
SCREENSHOT_ENCODINGS: dict[str, Callable[[Frame], str]] = {
    ".svg": lambda frame: frame.svg(),
    ".txt": lambda frame: frame.text(ansi=True),
}


@dataclass(frozen=True, slots=True)
class Screenshot(_Control):
    """
    Take a "screenshot" of the rendered UI,
    and pass it to the given `handler` callback function as a [`Frame`][counterweight.output.Frame],
    which the handler can encode as an SVG image or as text.

    The screenshot is taken at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the screenshot is taken
    (but the screenshot will still be of the UI from *before* the next render occurs!).
    Every screenshot requested in the same cycle receives the same frame.
    """

    handler: Callable[[Frame], Awaitable[None] | None]

    @classmethod
    def to_file(cls, path: Path) -> Screenshot:
        """
        A convenience method for producing a `Screenshot` that writes to the given `path`,
        encoded according to its suffix:
        `.svg` for an SVG image, or `.txt` for text with ANSI escape codes for colors and styles.

        Parameters:
            path: The path to write the screenshot to.
                Parent directories will be created if they do not exist.

        Raises:
            ValueError: If the path's suffix is neither `.svg` nor `.txt`.
        """
        try:
            encode = SCREENSHOT_ENCODINGS[path.suffix]
        except KeyError:
            raise ValueError(
                f"Can't tell how to encode a screenshot as {path.name!r}: "
                f"use a path ending in one of {sorted(SCREENSHOT_ENCODINGS)}"
            ) from None

        def handler(frame: Frame) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encode(frame))

        return cls(handler=handler)

    @classmethod
    def to_stream(cls, stream: TextIO | None = None, ansi: bool = True) -> Screenshot:
        """
        A convenience method for producing a `Screenshot` that prints the frame as text to the given `stream`.

        Parameters:
            stream: The stream to print to. Defaults to `sys.stderr`.
            ansi: Whether to include ANSI escape codes for colors and styles.
        """
        target = stream if stream is not None else sys.stderr

        def handler(frame: Frame) -> None:
            print(frame.text(ansi=ansi), file=target, flush=True)

        return cls(handler=handler)


@dataclass(frozen=True, slots=True)
class Suspend(_Control):
    """
    Suspend the application while the handler function is running.

    The application will be suspended (and then resumed) at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the application is suspended.
    """

    handler: Callable[[], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class ToggleBorderHealing(_Control):
    """
    Toggle whether border healing occurs.
    """


@dataclass(frozen=True, slots=True)
class FocusNext(_Control):
    """
    Move focus to the next visible component in the focus order, in tree order, wrapping from the last to the first.
    From nothing focused, or from focus outside `within`, it focuses the first.
    From a focused component that's out of the focus order (see `in_focus_order` on
    [`use_focus`][counterweight.hooks.use_focus]), it moves from that component's place in tree order.
    It does nothing if `within` has unmounted or holds no visible component in the focus order.
    """

    within: Subtree | None = None
    """
    The element whose focusable descendants, and itself if it's focusable, focus moves among,
    usually the [`subtree`][counterweight.events.Receiver.subtree] of the handler's receiver,
    or `None` for the whole tree.
    """


@dataclass(frozen=True, slots=True)
class FocusPrevious(_Control):
    """
    Move focus to the previous visible component in the focus order, in tree order, wrapping from the first to the last.
    From nothing focused, or from focus outside `within`, it focuses the last.
    Otherwise it behaves like [`FocusNext`][counterweight.controls.FocusNext].
    """

    within: Subtree | None = None
    """
    The element whose focusable descendants, and itself if it's focusable, focus moves among,
    or `None` for the whole tree.
    """


@dataclass(frozen=True, slots=True)
class FocusOn(_Control):
    """
    Focus the component whose [`use_focus`][counterweight.hooks.use_focus] has `handle`,
    whether or not it's in the focus order.
    It does nothing if that component hasn't mounted yet, has unmounted, is hidden, or is unfocusable.
    """

    handle: FocusHandle


@dataclass(frozen=True, slots=True)
class ClearFocus(_Control):
    """
    Clear focus, so key presses go to the root component.
    """


@dataclass(frozen=True, slots=True)
class AdvanceClock(_Control):
    """
    Move the application's clock forward by `by`, as if that much more time had passed,
    and render the components whose [`use_clock`][counterweight.hooks.use_clock] that makes due.

    This is primarily useful in an autopilot, with a [`frozen_clock`][counterweight.clock.frozen_clock],
    to show how an app changes over time without waiting for it.
    """

    by: timedelta


@dataclass(frozen=True, slots=True)
class ScrollTo(_Control):
    """
    Scroll the scroll container `target` names so its offset is `x` and `y`,
    as the web's [`scrollTo`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollTo) does,
    leaving an axis given as `None` where it is.
    The offset is clamped to the range the container scrolls through, from 0 to its
    [`max_offset`][counterweight.geometry.Scroll.max_offset],
    so a large `y` scrolls to the end.

    It applies to the layout of the next render, before that render paints,
    after [anchoring](../layout/scrolling.md#keeping-the-content-in-view) and sticking to the end,
    and in order with the other scroll controls returned since the last render,
    so a handler that returns it beside a state change scrolls the content that change lays out.
    It does nothing if `target` names no mounted, visible scroll container then.
    """

    target: ElementHandle | Subtree
    """
    The scroll container, by the [`ElementHandle`][counterweight.focus.ElementHandle] passed to its `handle`,
    or by the [`subtree`][counterweight.events.Receiver.subtree] of a handler's receiver.
    """
    x: int | None = None
    y: int | None = None

    def destination(self, offset: Position) -> Position:
        """Where this moves a container scrolled to `offset`, before clamping."""
        return Position(offset.x if self.x is None else self.x, offset.y if self.y is None else self.y)


@dataclass(frozen=True, slots=True)
class ScrollBy(_Control):
    """
    Scroll the scroll container `target` names by `x` columns and `y` rows,
    as the web's [`scrollBy`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollBy) does:
    positive values move toward the end of the content, and negative ones toward its start.
    The offset is clamped, and the control applied, as [`ScrollTo`][counterweight.controls.ScrollTo]'s is.
    """

    target: ElementHandle | Subtree
    """The scroll container, named as [`ScrollTo`][counterweight.controls.ScrollTo] names it."""
    x: int = 0
    y: int = 0

    def destination(self, offset: Position) -> Position:
        """Where this moves a container scrolled to `offset`, before clamping."""
        return Position(offset.x + self.x, offset.y + self.y)


ScrollAlignment = Literal["start", "center", "end", "nearest"]


@dataclass(frozen=True, slots=True)
class ScrollIntoView(_Control):
    """
    Scroll each scroll container above the element `target` names so the element's border box is in view,
    from the innermost container out, as the web's
    [`scrollIntoView`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView) does,
    aligning it as `block` says vertically and as `inline` says horizontally, with the web's defaults.
    On each axis, `"start"` puts the element's start edge at the start edge of the container's view,
    `"center"` its center at the view's center, and `"end"` its end edge at the view's end edge.
    `"nearest"` does whichever of `"start"` and `"end"` scrolls least,
    and doesn't scroll at all if the element is already wholly in view, or covers the whole view.
    Each offset is clamped to the range its container scrolls through.

    It applies as [`ScrollTo`][counterweight.controls.ScrollTo] does, to the layout of the next render,
    so a handler that returns it beside a state change, such as moving a highlight through a long list,
    shows the scroll in the same frame as the change.
    The element `target` names is the one with that handle in the next render,
    so a handle moved onto a newly highlighted element names the new one.
    It does nothing if `target` names no mounted, visible element then,
    and it stops at an element with [`clip_to_screen`](../layout/clipping.md#escaping-every-clip),
    since no container above that element clips it.
    """

    target: ElementHandle | Subtree
    """The element, named as [`ScrollTo`][counterweight.controls.ScrollTo] names a scroll container."""
    block: ScrollAlignment = "start"
    """Where to put the element vertically."""
    inline: ScrollAlignment = "nearest"
    """Where to put the element horizontally."""


AnyControl = Union[
    Quit,
    Bell,
    Screenshot,
    Suspend,
    ToggleBorderHealing,
    FocusNext,
    FocusPrevious,
    FocusOn,
    ClearFocus,
    AdvanceClock,
    ScrollTo,
    ScrollBy,
    ScrollIntoView,
]
