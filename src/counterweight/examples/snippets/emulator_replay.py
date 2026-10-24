"""
Terminals: Terminal emulators

Output written ahead of time replayed through an emulator, and a program's colors on a light theme.
"""

import asyncio
import sys
from collections.abc import Sequence
from datetime import timedelta
from functools import cache

from more_itertools import last

from counterweight import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.emulator import Screen
from counterweight.hooks import use_clock
from counterweight.painters import ScreenView
from counterweight.styles import Color
from counterweight.styles import Style
from counterweight.styles.utilities import *
from counterweight.widgets import TerminalStyles

# --8<-- [start:replay]

type RecordedOutput = Sequence[tuple[timedelta, bytes]]
"""What a program wrote, in chunks, each with how long after the program started it wrote it."""


def replay(output: RecordedOutput, columns: int, rows: int) -> tuple[tuple[timedelta, Screen], ...]:
    """What the terminal showed after each chunk of `output`, with when it was written."""
    with Emulator(columns, rows, on_reply=lambda reply: None) as emulator:
        screens = []
        for at, chunk in output:
            emulator.feed(chunk)
            screens.append((at, emulator.snapshot()))
        return tuple(screens)


TICK = timedelta(milliseconds=100)


@component
def replayed(screens: tuple[tuple[timedelta, Screen], ...], style: Style = default) -> Canvas:
    elapsed = use_clock(TICK).since_mount
    screen = last((screen for at, screen in screens if at <= elapsed), screens[0][1])
    return Canvas(painter=ScreenView(screen, show_cursor=True), style=style)


# --8<-- [end:replay]


def goto(row: int, column: int) -> str:
    return f"\x1b[{row};{column}H"


def vim_session(columns: int, rows: int) -> RecordedOutput:
    """
    Output in the style of vim's, opening a line in a small file, typing into it, and saving it,
    written by hand rather than recorded, so the docs don't depend on vim.
    """
    keep = ["def greet(name):", '    return f"Hello, {name}!"', ""]
    shown = [
        "\x1b[35mdef\x1b[0m \x1b[36mgreet\x1b[0m(name):",
        '    \x1b[35mreturn\x1b[0m \x1b[32mf"Hello, {name}!"\x1b[0m',
        "",
    ]
    typed = 'print(greet("world"))'

    def number(line: int) -> str:
        return f"\x1b[33m{line:>3} \x1b[0m"

    def status(text: str, line: int, column: str) -> str:
        return goto(rows, 1) + "\x1b[K" + text + goto(rows, columns - 17) + f"{line},{column}".ljust(10) + "All"

    def size(lines: list[str]) -> str:
        return f"{len(lines)}L, {sum(len(line) + 1 for line in lines)}B"

    chunks = [
        (
            timedelta(),
            "\x1b[?1049h\x1b[H\x1b[2J"
            + "".join(goto(row, 1) + number(row) + line for row, line in enumerate(shown, start=1))
            + "".join(goto(row, 1) + "\x1b[94m~\x1b[0m" for row in range(len(shown) + 1, rows))
            + status(f'"greet.py" {size(keep)}', 3, "0-1")
            + goto(3, 5),
        ),
        (
            timedelta(milliseconds=800),
            goto(4, 1) + number(4) + status("\x1b[1m-- INSERT --\x1b[0m", 4, "1") + goto(4, 5),
        ),
    ]
    start = timedelta(milliseconds=1200)
    in_string = False
    for index, character in enumerate(typed):
        if character == '"':
            in_string = not in_string
        color = "\x1b[32m" if in_string or character == '"' else ""
        chunks.append(
            (
                start + index * TICK,
                goto(4, 5 + index)
                + color
                + character
                + "\x1b[0m"
                + status("\x1b[1m-- INSERT --\x1b[0m", 4, str(index + 2))
                + goto(4, 6 + index),
            )
        )
    end = start + len(typed) * TICK
    saved = [*keep, typed]
    chunks += [
        (end + 4 * TICK, status("", 4, str(len(typed))) + goto(4, 4 + len(typed))),
        (end + 10 * TICK, goto(rows, 1) + "\x1b[K:"),
        (end + 12 * TICK, "w"),
        (end + 16 * TICK, status(f'"greet.py" {size(saved)} written', 4, str(len(typed))) + goto(4, 4 + len(typed))),
    ]
    return [(at, text.encode()) for at, text in chunks]


@cache
def vim_screens() -> tuple[tuple[timedelta, Screen], ...]:
    """The screens of the vim session, replayed the first time they're shown rather than when the module is imported."""
    return replay(vim_session(columns=50, rows=12), columns=50, rows=12)


@component
def vim() -> Div:
    styles = TerminalStyles()
    return Div(children=(replayed(vim_screens(), style=styles.box_style(size(52, 14), is_focused=True)),))


COLORS = (
    "palette \x1b[40m  \x1b[41m  \x1b[42m  \x1b[43m  \x1b[44m  \x1b[45m  \x1b[46m  \x1b[47m  \x1b[0m\r\n"
    "bright  \x1b[100m  \x1b[101m  \x1b[102m  \x1b[103m  \x1b[104m  \x1b[105m  \x1b[106m  \x1b[107m  \x1b[0m\r\n"
    "256     "
    + "".join(f"\x1b[48;5;{index}m " for index in range(196, 232, 3))
    + "".join(f"\x1b[48;5;{index}m " for index in range(232, 256, 6))
    + "\x1b[0m\r\n"
    "rgb     "
    + "".join(f"\x1b[48;2;{16 * step};{96 + 8 * step};{255 - 12 * step}m " for step in range(16))
    + "\x1b[0m\r\n"
    "default plain text\r\n"
    "inverse \x1b[7m swapped \x1b[27m"
).encode()


# --8<-- [start:colors]


@cache
def snapshot(output: bytes, foreground: Color, background: Color) -> Screen:
    with Emulator(26, 6, on_reply=lambda reply: None, foreground=foreground, background=background) as emulator:
        emulator.feed(output)
        return emulator.snapshot()


@component
def themed_output(screen: Screen) -> Canvas:
    # The theme's colors again, for the cells in the program's default colors.
    theme = text_color("slate", 900) | text_bg("slate", 100) | content_color("slate", 100)
    return Canvas(painter=ScreenView(screen), style=size(28, 6) | pad_x(1) | theme)


@component
def colors() -> Div:
    untold = snapshot(COLORS, foreground=Color.from_name("white"), background=Color.from_name("black"))
    # Told the theme's colors, for the cells whose colors the program swapped.
    themed = snapshot(COLORS, foreground=slate_900, background=slate_100)
    return Div(
        style=row | gap(2),
        children=tuple(
            Div(style=col, children=(Text(content=label, style=text_color("slate", 400)), themed_output(screen)))
            for label, screen in (("The emulator's defaults", untold), ("The theme's colors", themed))
        ),
    )


# --8<-- [end:colors]


ROOTS = (colors, vim)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

STILLS = [Still("emulator-colors", colors(), (58, 7))]

DEMOS = [
    Demo(
        "emulator-replay",
        vim(),
        (52, 14),
        steps=[*[AdvanceClock(by=TICK)] * (vim_session(50, 12)[-1][0] // TICK), AdvanceClock(by=timedelta(seconds=3))],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
