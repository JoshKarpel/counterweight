from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import indent as indent_svg


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


@dataclass(frozen=True, slots=True)
class Screenshot(_Control):
    """
    Take a "screenshot" of the rendered UI,
    using the given `handler` callback function.
    The screenshot is passed to the `handler` as an
    [`ElementTree`][xml.etree.ElementTree.ElementTree]
    containing an SVG representation of the UI.

    The screenshot is taken at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the screenshot is taken
    (but the screenshot will still be of the UI from *before* the next render occurs!).
    """

    handler: Callable[[ElementTree], Awaitable[None] | None]

    @classmethod
    def to_file(cls, path: Path, indent: int | None = None) -> Screenshot:
        """
        A convenience method for producing a `Screenshot`
        that writes the resulting SVG to the given `path`.

        Parameters:
            path: The path to write the SVG to.
                Parent directories will be created if they do not exist.
            indent: The number of spaces to indent the SVG by (for readability).
                If `None`, the SVG will not be indented.
        """

        def handler(et: ElementTree) -> None:
            if indent:
                indent_svg(et, space=" " * indent)

            path.parent.mkdir(parents=True, exist_ok=True)

            with path.open("w") as f:
                et.write(f, encoding="unicode")

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
