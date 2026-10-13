import asyncio
import sys
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ScrollBy
from counterweight.elements import Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Pasted, Receiver
from counterweight.handlers import first, focus_receiver_on_press, scroll_on_wheel, tab_focus
from counterweight.headless import use_text_input
from counterweight.hooks import ElementHandle, Setter, use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle
from counterweight.styles.utilities import *
from counterweight.widgets import text_input
from docs.examples.screenshot_spec import ScreenshotSpec

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


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


TAB = KeyPressed(key=Key.Tab)

SCREENSHOTS = [
    ScreenshotSpec(search(), "text-input-search", (30, 8)),
    ScreenshotSpec(
        search(), "text-input-search-scrolled", (30, 8), events=(KeyPressed(key=Key.Down), KeyPressed(key=Key.Down))
    ),
    ScreenshotSpec(search(), "text-input-search-typed", (30, 8), events=(*typed("an"),)),
    ScreenshotSpec(
        search(),
        "text-input-search-cursor",
        (30, 8),
        events=(
            *typed("mngo"),
            KeyPressed(key=Key.Left),
            KeyPressed(key=Key.Left),
            KeyPressed(key=Key.Left),
            *typed("a"),
        ),
    ),
    ScreenshotSpec(sign_up(), "text-input-sign-up", (30, 6)),
    ScreenshotSpec(
        sign_up(),
        "text-input-sign-up-filled",
        (30, 6),
        events=(Pasted(text="Ada Lovelace"), TAB, *typed("3x6")),
    ),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (search, sign_up)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else search()))
