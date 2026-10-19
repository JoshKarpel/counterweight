"""
Hooks: use_memo

A file browser that sorts and filters its files only when they or the filter change.
"""

import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import toggle
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_memo
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

PATHS = (
    "src/app.py",
    "mkdocs.yml",
    "tests/test_app.py",
    "pyproject.toml",
    "docs/index.md",
)

# --8<-- [start:example]


@component
def file_list(paths: tuple[str, ...]) -> Div:
    use_focus(auto_focus=True)
    descending, set_descending = use_state(False)

    ordered = use_memo(lambda: sorted(paths, reverse=descending), deps=(paths, descending))

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="r"):
                set_descending(toggle)
                return ()
            case _:
                return None

    return Div(
        style=col,
        on_input=on_input,
        children=(
            Text(content=f"{'Z to A' if descending else 'A to Z'} (r reverses)", style=text_color("slate", 400)),
            *(Text(content=path) for path in ordered),
        ),
    )


@component
def browser() -> Div:
    tick = use_clock(timedelta(seconds=1))
    seconds = tick.since_mount // timedelta(seconds=1)

    return Div(
        style=col | border | border_lightrounded | pad_x(1),
        children=(
            Text(content=f"Open for {seconds} s", style=text_color("amber", 400)),
            file_list(PATHS),
        ),
    )


# --8<-- [end:example]


ROOTS = (browser,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Still

STILLS = [
    Still(
        "use-memo-file-list", browser(), (30, 9), steps=[AdvanceClock(by=timedelta(seconds=12)), KeyPressed(key="r")]
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(browser()))
