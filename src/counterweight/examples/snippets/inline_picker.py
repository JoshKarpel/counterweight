"""
Inline apps: A picker

A branch picker below the prompt, as `fzf` is: typing narrows the branches, Up and Down move between them,
and Enter prints the one picked to standard output and erases the picker.
It draws on standard error, so `git switch "$(python inline_picker.py)"` switches to the branch picked.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from dataclasses import replace

from counterweight import Inline
from counterweight import app
from counterweight.components import component
from counterweight.controls import Print
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.headless import use_text_input
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *

VIEWPORT = Inline(keep_last_frame=False)

BRANCHES = (
    "main",
    "feature/inline-rendering",
    "feature/print-above-the-region",
    "fix/rewrap-on-resize",
    "fix/mouse-offset",
    "docs/inline-apps",
    "release/0.2",
)

SHOWN = 5

CURSOR = (text_color("slate", 900) | text_bg("sky", 300)).text_style


def matches(typed: str, branches: tuple[str, ...]) -> tuple[str, ...]:
    """The branches that hold the letters typed, in order, as `fzf` matches."""

    def holds(branch: str) -> bool:
        letters = iter(branch)
        return all(letter in letters for letter in typed)

    return tuple(branch for branch in branches if holds(branch))


@dataclass(frozen=True, slots=True)
class Search:
    typed: str
    highlighted: int

    def edited(self, typed: str) -> Search:
        return self if typed == self.typed else Search(typed=typed, highlighted=0)


# --8<-- [start:picker]


@component
def branch_picker() -> Div:
    search, set_search = use_state(Search(typed="", highlighted=0))
    field = use_text_input(search.typed, lambda edit: set_search(lambda s: s.edited(edit(s.typed))), auto_focus=True)
    shown = matches(search.typed, BRANCHES)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Down) if shown:
                set_search(lambda s: replace(s, highlighted=min(s.highlighted + 1, len(shown) - 1)))
                return ()
            case KeyPressed(key=Key.Up) if shown:
                set_search(lambda s: replace(s, highlighted=max(s.highlighted - 1, 0)))
                return ()
            case KeyPressed(key=Key.Enter) if shown:
                return Print(Text(content=shown[search.highlighted])), Quit()
            case KeyPressed(key=Key.Escape):
                return Quit()
            case _:
                return None

    return Div(
        style=col,
        on_input=first(on_input, field.on_input),
        children=(
            Div(
                style=row,
                children=(
                    Text(content="branch> ", style=text_color("sky", 300) | text_wrap_none),
                    Text(content=field.before_cursor, style=text_wrap_none),
                    Text(content=field.at_cursor, style=text_wrap_none | Style(text_style=CURSOR)),
                    Text(content=field.after_cursor, style=text_wrap_none),
                ),
            ),
            *(
                Text(
                    content=f"{'▸' if index == search.highlighted else ' '} {branch}",
                    style=text_wrap_none
                    | (text_bg("sky", 800) | text_bold if index == search.highlighted else text_color("slate", 300)),
                )
                for index, branch in enumerate(shown[:SHOWN])
            ),
            Text(content=f"  {len(shown)}/{len(BRANCHES)}", style=text_color("slate", 500)),
        ),
    )


# --8<-- [end:picker]


ROOTS = (branch_picker,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

DIMENSIONS = (48, 4)

STILLS = [Still("inline-picker", branch_picker(), DIMENSIONS, steps=[*typed("fix")], viewport=VIEWPORT)]

DEMOS = [
    Demo(
        "inline-picker",
        branch_picker(),
        (48, 8),
        steps=[
            *paced(
                [*typed("fix"), KeyPressed(key=Key.Down), KeyPressed(key=Key.Enter)],
                pause=AdvanceClock(by=timedelta(milliseconds=400)),
            ),
        ],
        viewport=VIEWPORT,
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(branch_picker(), viewport=VIEWPORT, output_stream=sys.stderr))
