"""
Cookbook: Pickers

Settings whose F2 and F3 open a picker over the corner of the screen,
a field that narrows a list of options in sections, chosen with the arrow keys and Enter or a click.
"""

from __future__ import annotations

import asyncio
import glob
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from fnmatch import fnmatchcase
from functools import partial

from counterweight import app
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import ClearFocus
from counterweight.controls import FocusOn
from counterweight.controls import ScrollIntoView
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.events import response_controls
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import on_click
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import use_text_input
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *

CURSOR = (text_color("slate", 900) | text_bg("sky", 300)).text_style


def matches(text: str, candidates: tuple[str, ...]) -> list[str]:
    pattern = f"*{'*'.join(glob.escape(c) for c in text.lower())}*"
    found = [candidate for candidate in candidates if fnmatchcase(candidate.lower(), pattern)]
    # The one the text names exactly first, so typing a whole name and pressing Enter chooses it.
    return sorted(found, key=lambda candidate: candidate.lower() != text.lower())


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    highlighted: int
    is_dismissed: bool

    def edited(self, text: str) -> Completion:
        return self if text == self.text else Completion(text=text, highlighted=0, is_dismissed=False)


# --8<-- [start:sections]


@dataclass(frozen=True, slots=True)
class Section:
    """A run of a picker's options, under a bar with its `title`, which is chosen as an option is, or under no bar."""

    title: str | None
    options: tuple[str, ...]

    @property
    def names(self) -> tuple[str, ...]:
        """What the section lists, in order: its bar's title, if it has one, then its options."""
        return (*(() if self.title is None else (self.title,)), *self.options)


@dataclass(frozen=True, slots=True)
class Choice:
    label: str
    sections: tuple[Section, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(*section.names for section in self.sections)

    @property
    def titles(self) -> frozenset[str]:
        return frozenset(section.title for section in self.sections if section.title is not None)

    def option_for(self, name: str) -> str:
        """The option choosing `name` picks: for a bar, the newest of its section, which it lists last."""
        return next((section.options[-1] for section in self.sections if section.title == name), name)


# Choosing a bar chooses the newest of its section, as `uv python install pypy` does.
PYTHON = Choice(
    label="Python",
    sections=(
        Section(title="CPython", options=("3.13", "3.14", "3.15", "3.15t")),
        Section(title="PyPy", options=("pypy3.10", "pypy3.11")),
    ),
)
INDEX = Choice(label="Index", sections=(Section(title=None, options=("pypi", "testpypi", "pytorch-cpu")),))


# --8<-- [end:sections]

# --8<-- [start:picking]


@dataclass(frozen=True, slots=True, eq=False)
class Picking:
    """One opening of a picker: what it offers, and handles of its own."""

    choice: Choice
    focus: FocusHandle = field(default_factory=FocusHandle)
    highlighted: ElementHandle = field(default_factory=ElementHandle)

    def opened(self) -> tuple[AnyControl, ...]:
        """What the key that opens the picker returns, so the frame it opens in focuses it and shows its current option."""
        return FocusOn(self.focus), ScrollIntoView(self.highlighted, block="nearest")


# --8<-- [end:picking]

# --8<-- [start:picker]


@component
def picker(picking: Picking, current: str, choose: Callable[[str], None], close: Callable[[], None]) -> Div:
    choice = picking.choice
    names = choice.names
    completion, set_completion = use_state(Completion(text="", highlighted=names.index(current), is_dismissed=False))

    def edit(edit_text: Callable[[str], str]) -> None:
        set_completion(lambda c: c.edited(edit_text(c.text)))

    field = use_text_input(completion.text, edit, handle=picking.focus)
    shown = matches(completion.text, names)

    def chosen(name: str) -> InputResponse:
        choose(name)
        close()
        return ClearFocus()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        highlighted_in_view = ScrollIntoView(picking.highlighted, block="nearest")
        match event:
            case KeyPressed(key=Key.Down) if shown:
                set_completion(lambda c: replace(c, highlighted=(c.highlighted + 1) % len(shown)))
            case KeyPressed(key=Key.Up) if shown:
                set_completion(lambda c: replace(c, highlighted=(c.highlighted - 1) % len(shown)))
            case KeyPressed(key=Key.Enter | Key.Tab) if shown:
                return chosen(shown[completion.highlighted])
            case KeyPressed(key=Key.Escape):
                close()
                return ClearFocus()
            case _:
                if (edited := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*edited, highlighted_in_view)
        return highlighted_in_view

    def option_row(index: int, name: str) -> Text:
        marker = "▸" if name == current else " "
        is_bar = name in choice.titles
        return Text(
            content=f"{marker}── {name} ──" if is_bar else f"{marker} {name}",
            style=text_wrap_none
            | (text_bold if is_bar else text_color("slate", 300))
            | (text_bg("sky", 800) if index == completion.highlighted else Style()),
            handle=picking.highlighted if index == completion.highlighted else None,
            on_input=on_click(partial(chosen, name)),
        )

    return Div(
        style=position_absolute
        | inset_right(1)
        | inset_top(1)
        | z(1)
        | width(20)
        | col
        | border
        | border_lightrounded
        | border_color("amber", 300)
        | pad_x(1)
        | content_color("slate", 900)
        | padding_color("slate", 900),
        on_input=first(on_input, focus_receiver_on_press),
        children=(
            Text(content=choice.label, style=text_color("slate", 400)),
            Div(
                style=row | overflow_x_scroll | stick_to_end_x | text_bg("slate", 700),
                on_input=field.on_press,
                children=(
                    Text(content="> ", style=text_wrap_none),
                    Text(content=field.before_cursor, style=text_wrap_none),
                    Text(
                        content=field.at_cursor,
                        style=text_wrap_none | Style(text_style=CURSOR),
                        handle=field.cursor_cell,
                    ),
                    Text(content=field.after_cursor, style=text_wrap_none),
                ),
            ),
            Div(
                style=col | max_height(5) | overflow_y_scroll,
                on_input=scroll_on_wheel(1),
                children=tuple(option_row(index, name) for index, name in enumerate(shown))
                or (Text(content="nothing matches", style=text_color("slate", 400)),),
            ),
        ),
    )


# --8<-- [end:picker]

# --8<-- [start:settings]


@component
def settings() -> Div:
    python, set_python = use_state("3.15")
    index, set_index = use_state("pypi")
    nothing_picked: Picking | None = None
    picking, set_picking = use_state(nothing_picked)
    chosen = {PYTHON: (python, set_python), INDEX: (index, set_index)}

    def choose(choice: Choice, name: str) -> None:
        chosen[choice][1](choice.option_for(name))

    def open_picker(choice: Choice) -> tuple[AnyControl, ...]:
        opening = Picking(choice)
        set_picking(opening)
        return opening.opened()

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.F2):
                return open_picker(PYTHON)
            case KeyPressed(key=Key.F3):
                return open_picker(INDEX)
            case _:
                return None

    return Div(
        style=full | col | pad_x(1),
        on_input=on_input,
        children=(
            Text(content=f"Python {python}", style=text_color("teal", 300)),
            Text(content=f"Index  {index}", style=text_color("teal", 300)),
            Text(content="F2 picks the Python and F3 the index", style=text_color("slate", 400) | text_wrap_pretty),
            *(
                ()
                if picking is None
                else (
                    picker(
                        picking,
                        chosen[picking.choice][0],
                        partial(choose, picking.choice),
                        partial(set_picking, None),
                    ).with_key(picking.choice.label),
                )
            ),
        ),
    )


# --8<-- [end:settings]


ROOTS = (settings,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

F2 = KeyPressed(key=Key.F2)
F3 = KeyPressed(key=Key.F3)
DOWN = KeyPressed(key=Key.Down)
ENTER = KeyPressed(key=Key.Enter)
DIMENSIONS = (40, 10)

STILLS = [
    Still("picker-open", settings(), DIMENSIONS, steps=[F2]),
    Still("picker-typed", settings(), DIMENSIONS, steps=[F2, *typed("pypy")]),
    Still("picker-switched", settings(), DIMENSIONS, steps=[F2, F3, *typed("cpu")]),
]

DEMOS = [
    Demo(
        "picker",
        settings(),
        DIMENSIONS,
        steps=[
            *paced(
                [F2, DOWN, ENTER, F2, *typed("pypy"), ENTER, F2, F3, *typed("cpu"), ENTER],
                pause=AdvanceClock(by=timedelta(milliseconds=500)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(settings()))
