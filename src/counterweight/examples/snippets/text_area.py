"""
Headless components: use_text_area

A chat prompt and a notes field whose text wraps onto rows.
"""

import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass

from counterweight import app
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import use_text_area
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from counterweight.widgets import text_area

# --8<-- [start:hook]

CURSOR = (text_color("slate", 900) | text_bg("amber", 300)).text_style


@dataclass(frozen=True, slots=True)
class Conversation:
    messages: tuple[str, ...]
    draft: str


@component
def composer(draft: str, edit_draft: Callable[[Callable[[str], str]], None], send: Callable[[], None]) -> Text:
    rects = use_rects()
    field = use_text_area(draft, edit_draft, width=rects.content.width, auto_focus=True)

    def on_enter(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                send()
                return ()
            case _:
                return None

    return Text(
        content=(
            Chunk(content=field.before_cursor),
            Chunk(content=field.at_cursor, style=CURSOR),
            Chunk(content=field.after_cursor),
        ),
        style=border | border_lightrounded | border_color("amber", 400) | pad_x(1) | text_wrap_none,
        on_input=first(field.on_input, field.on_press, on_enter),
    )


@component
def chat() -> Div:
    conversation, set_conversation = use_state(Conversation(messages=(), draft=""))

    def edit_draft(edit: Callable[[str], str]) -> None:
        set_conversation(lambda c: Conversation(messages=c.messages, draft=edit(c.draft)))

    def send() -> None:
        set_conversation(lambda c: Conversation(messages=(*c.messages, c.draft), draft=""))

    return Div(
        style=col | size(34, 9) | gap(1),
        children=(
            Div(
                style=fill(1) | col | justify_children_end | gap(1) | overflow_y_scroll | stick_to_end_y,
                on_input=scroll_on_wheel(1),
                children=tuple(
                    Text(content=message, style=text_wrap_pretty | text_color("slate", 400))
                    for message in conversation.messages
                ),
            ),
            composer(conversation.draft, edit_draft, send),
        ),
    )


# --8<-- [end:hook]

# --8<-- [start:widget]


@component
def notes() -> Div:
    text, set_text = use_state("")
    return Div(
        style=col | width(30),
        children=(
            text_area(
                text,
                set_text,
                placeholder="Notes",
                style=max_height(6),
                enter_inserts_newline=True,
                auto_focus=True,
            ),
        ),
    )


# --8<-- [end:widget]


ROOTS = (chat, notes)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.events import Pasted
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

CTRL_J = KeyPressed(key=Key.ControlJ)
ENTER = KeyPressed(key=Key.Enter)
DRAFT = (*typed("Rows wrap to fit the box as you type"), CTRL_J, *typed("and Ctrl+J starts a line"))
CHATTED = (*DRAFT, ENTER, *typed("Older messages scroll up"), ENTER, *typed("as new ones arrive"), ENTER)
GROCERIES = ("Milk", "Eggs", "Flour", "Butter", "Sugar", "Lemons")

STILLS = [
    Still("text-area-chat-draft", chat(), (34, 9), steps=DRAFT),
    Still("text-area-chat-sent", chat(), (34, 9), steps=(*DRAFT, ENTER)),
    Still("text-area-chat-scrolled", chat(), (34, 9), steps=CHATTED),
    Still("text-area-notes", notes(), (30, 6)),
    Still(
        "text-area-notes-filled",
        notes(),
        (30, 6),
        steps=(*typed("Milk"), ENTER, *typed("Eggs"), ENTER, *typed("Flour")),
    ),
    Still(
        "text-area-notes-scrolled",
        notes(),
        (30, 6),
        steps=tuple(event for item in GROCERIES for event in (*typed(item), ENTER))[:-1],
    ),
    Still("text-area-notes-pasted", notes(), (30, 6), steps=(Pasted(text="if done:\n\tship()\n\treturn"),)),
]


DEMOS = [
    Demo(
        "text-area-chat",
        chat(),
        (34, 9),
        steps=[
            *paced(CHATTED, pause=AdvanceClock(by=timedelta(milliseconds=80))),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
