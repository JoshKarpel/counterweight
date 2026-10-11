from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, Union

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


AnyControl = Union[
    Quit,
    Bell,
    Screenshot,
    Suspend,
    ToggleBorderHealing,
]
