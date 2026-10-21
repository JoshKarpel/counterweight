"""
Headless components: use_text_input

A fruit search, a sign-up form, a command line, and restyled fields.
"""

import asyncio
import sys
from collections.abc import Callable

from counterweight import app
from counterweight.components import component
from counterweight.controls import ScrollBy
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import scroll_on_wheel
from counterweight.handlers import tab_focus
from counterweight.headless import use_text_input
from counterweight.hooks import Setter
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.utilities import *
from counterweight.widgets import TextFieldStyles
from counterweight.widgets import text_input

# --8<-- [start:hook]

FRUITS = ("apple", "banana", "cherry", "grape", "lemon", "mango", "orange", "papaya")

CURSOR = (text_color("slate", 900) | text_bg("amber", 300)).text_style


@component
def search_box(query: str, set_query: Setter[str]) -> Text:
    field = use_text_input(query, set_query, auto_focus=True)
    cursor = CURSOR if field.focus.is_focused else CellStyle()
    return Text(
        content=(
            Chunk(content="search: ", style=text_color("amber", 400).text_style),
            Chunk(content=field.before_cursor),
            Chunk(content=field.at_cursor, style=cursor),
            Chunk(content=field.after_cursor),
        ),
        on_input=first(field.on_input, focus_receiver_on_press),
    )


@component
def search() -> Div:
    query, set_query = use_state("")
    results, _ = use_state(ElementHandle)
    matches = [fruit for fruit in FRUITS if query in fruit]

    def scroll_results(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Up):
                return ScrollBy(results, y=-1)
            case KeyPressed(key=Key.Down):
                return ScrollBy(results, y=1)
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=scroll_results,
        children=(
            search_box(query, set_query),
            Div(
                style=col | max_height(5) | overflow_y_scroll,
                handle=results,
                on_input=scroll_on_wheel(1),
                children=(Text(content="\n".join(matches) or "no matches", style=text_color("slate", 400)),),
            ),
        ),
    )


# --8<-- [end:hook]

# --8<-- [start:widget]


def digits_only(set_value: Setter[str]) -> Callable[[Callable[[str], str]], None]:
    def set_digits(edit: Callable[[str], str]) -> None:
        set_value(lambda value: edited if (edited := edit(value)).isdigit() or not edited else value)

    return set_digits


@component
def sign_up() -> Div:
    name, set_name = use_state("")
    age, set_age = use_state("")
    return Div(
        style=col | width(30),
        on_input=tab_focus,
        children=(
            text_input(name, set_name, placeholder="Name", auto_focus=True),
            text_input(age, digits_only(set_age), placeholder="Age"),
        ),
    )


# --8<-- [end:widget]

# --8<-- [start:scrolling]


@component
def command_line() -> Div:
    command, set_command = use_state("")
    field = use_text_input(command, set_command, auto_focus=True)
    cursor = CURSOR if field.focus.is_focused else CellStyle()
    return Div(
        style=row | width(24),
        on_input=first(field.on_input, focus_receiver_on_press),
        children=(
            Text(content="$ ", style=text_color("amber", 400)),
            Div(
                style=row | overflow_x_scroll | stick_to_end_x,
                on_input=field.on_press,
                children=(
                    Text(content=field.before_cursor, style=text_wrap_none),
                    Text(
                        content=field.at_cursor,
                        style=text_wrap_none | Style(text_style=cursor),
                        handle=field.cursor_cell,
                    ),
                    Text(
                        content=field.after_cursor + (" " if field.cursor < len(command) else ""),
                        style=text_wrap_none,
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:scrolling]

# --8<-- [start:styles]

AMBER = TextFieldStyles(
    box=border | border_heavy | border_color("slate", 500) | pad_x(1),
    focused_box=border_color("amber", 400),
    cursor=(text_color("slate", 900) | text_bg("amber", 300)).text_style,
    placeholder=CellStyle(italic=True) | text_color("slate", 400).text_style,
)


@component
def amber_sign_up() -> Div:
    name, set_name = use_state("")
    email, set_email = use_state("")
    return Div(
        style=col | width(30),
        on_input=tab_focus,
        children=(
            text_input(name, set_name, placeholder="Name", styles=AMBER, auto_focus=True),
            text_input(email, set_email, placeholder="Email", styles=AMBER),
        ),
    )


# --8<-- [end:styles]


ROOTS = (search, sign_up, command_line, amber_sign_up)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.events import Pasted
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

TAB = KeyPressed(key=Key.Tab)
COMMAND = typed('git commit -m "Scroll long values"')

STILLS = [
    Still("text-input-search", search(), (30, 8)),
    Still("text-input-search-scrolled", search(), (30, 8), steps=(KeyPressed(key=Key.Down), KeyPressed(key=Key.Down))),
    Still("text-input-search-typed", search(), (30, 8), steps=(*typed("an"),)),
    Still(
        "text-input-search-cursor",
        search(),
        (30, 8),
        steps=(
            *typed("mngo"),
            KeyPressed(key=Key.Left),
            KeyPressed(key=Key.Left),
            KeyPressed(key=Key.Left),
            *typed("a"),
        ),
    ),
    Still("text-input-sign-up", sign_up(), (30, 6)),
    Still("text-input-sign-up-filled", sign_up(), (30, 6), steps=(Pasted(text="Ada Lovelace"), TAB, *typed("3x6"))),
    Still(
        "text-input-sign-up-long", sign_up(), (30, 6), steps=(Pasted(text="Augusta Ada King, Countess of Lovelace"),)
    ),
    Still("text-input-command", command_line(), (24, 1), steps=COMMAND),
    Still("text-input-command-home", command_line(), (24, 1), steps=(*COMMAND, KeyPressed(key=Key.Home))),
    Still("text-input-styled", amber_sign_up(), (30, 6), steps=(*typed("Ada"),)),
]

DEMOS = [
    Demo(
        "text-input-search",
        search(),
        (30, 8),
        steps=[
            *paced(
                [
                    KeyPressed(key=Key.Down),
                    KeyPressed(key=Key.Down),
                    *typed("an"),
                    KeyPressed(key=Key.Backspace),
                    KeyPressed(key=Key.Backspace),
                    *typed("ch"),
                ],
                pause=AdvanceClock(by=timedelta(milliseconds=300)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
