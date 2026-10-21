"""
Terminals: Pseudo-terminals

A program run on a pseudo-terminal, beside what an emulator shows of the bytes it wrote.
"""

import asyncio
import sys
from functools import cache
from typing import assert_never

from counterweight import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.emulator import Screen
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.painters import ScreenView
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.pseudoterminal import run_pty
from counterweight.styles.utilities import *

# --8<-- [start:example]

SCRIPT = """
for done in range(4):
    print(f"\\r[{'#' * done}{'.' * (3 - done)}]", end="")
print(" \\x1b[32mdone\\x1b[0m")
print("\\x1b[1mbold\\x1b[0m and \\x1b[31mred\\x1b[0m")
"""

COLUMNS, ROWS = 36, 3


@cache
def emulated(output: bytes) -> Screen:
    """
    What a terminal shows once a program has written `output` to it,
    the same `Screen` every time it's asked, since each emulator's snapshots are its own.
    """
    with Emulator(COLUMNS, ROWS, on_reply=lambda reply: None) as emulator:
        emulator.feed(output)
        return emulator.snapshot()


def describe(outcome: Exited | FailedToStart | None) -> str:
    match outcome:
        case None:
            return "Running..."
        case Exited(status=status):
            return f"Exited with status {status}"
        case FailedToStart(reason=reason):
            return f"Failed to start: {reason}"
        case _ as unreachable:
            assert_never(unreachable)


@component
def program(argv: tuple[str, ...] = (sys.executable, "-c", SCRIPT)) -> Div:
    output, set_output = use_state(b"")
    not_yet: Exited | FailedToStart | None = None
    outcome, set_outcome = use_state(not_yet)

    async def run() -> None:
        def on_output(chunk: bytes) -> None:
            set_output(lambda written: written + chunk)

        set_output(b"")
        set_outcome(None)
        set_outcome(await run_pty(argv, COLUMNS, ROWS, on_output=on_output))

    use_effect(run, deps=(argv,))

    def panel(title: str, content: Text | Canvas) -> Div:
        return Div(
            style=col | border | border_lightrounded | border_color("slate", 600) | pad_x(1),
            children=(Text(content=title, style=text_color("sky", 300)), content),
        )

    return Div(
        style=col | gap(1) | fit_content_width,
        children=(
            # A Text draws the control characters it holds as symbols, such as ␛ for escape and ␍ for carriage return.
            panel("What the program wrote", Text(content=output.decode(errors="replace"))),
            panel("What a terminal shows", Canvas(painter=ScreenView(emulated(output)), style=size(COLUMNS, ROWS))),
            Text(content=describe(outcome), style=text_color("slate", 500)),
        ),
    )


# --8<-- [end:example]


ROOTS = (program,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import WaitFor
from counterweight.examples.scenes import Still

STILLS = [
    Still(
        "pseudoterminals",
        program(),
        (44, 15),
        steps=[WaitFor(lambda frame: "Exited" in frame.text(ansi=False), timeout=timedelta(seconds=30))],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
