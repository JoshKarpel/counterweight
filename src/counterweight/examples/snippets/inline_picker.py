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
from counterweight.headless import Highlight
from counterweight.headless import subsequence_matches
from counterweight.headless import use_text_input
from counterweight.hooks import get_state
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


@dataclass(frozen=True, slots=True)
class Search:
    typed: str
    highlight: Highlight

    def edited(self, typed: str) -> Search:
        return self if typed == self.typed else Search(typed=typed, highlight=Highlight())


# --8<-- [start:picker]


def shown_for(typed: str) -> tuple[str, ...]:
    """The branches that hold the letters typed, in order, as `fzf` matches, as many as the picker shows."""
    return subsequence_matches(typed, BRANCHES)[:SHOWN]


@component
def branch_picker() -> Div:
    search, set_search = use_state(Search(typed="", highlight=Highlight()))
    field = use_text_input(
        search.typed, lambda edit: set_search(lambda s: s.edited(edit(s.typed))).typed, auto_focus=True
    )
    matched = subsequence_matches(search.typed, BRANCHES)
    highlighted = search.highlight.index_in(matched[:SHOWN])

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        now = get_state(set_search)
        now_shown = shown_for(now.typed)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key) if now_shown:
                by = 1 if key == Key.Down else -1
                set_search(replace(now, highlight=now.highlight.moved(now_shown, by, ends="stop")))
                return ()
            case KeyPressed(key=Key.Enter) if (index := now.highlight.index_in(now_shown)) is not None:
                return Print(Text(content=now_shown[index])), Quit()
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
                    content=f"{'▸' if index == highlighted else ' '} {branch}",
                    style=text_wrap_none
                    | (text_bg("sky", 800) | text_bold if index == highlighted else text_color("slate", 300)),
                )
                for index, branch in enumerate(matched[:SHOWN])
            ),
            Text(content=f"  {len(matched)}/{len(BRANCHES)}", style=text_color("slate", 500)),
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
