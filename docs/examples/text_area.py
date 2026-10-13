import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.handlers import first
from counterweight.headless import use_text_area
from counterweight.hooks import use_rects, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from counterweight.widgets import text_area
from docs.examples.screenshot_spec import ScreenshotSpec

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
        content=[
            Chunk(content=field.before_cursor),
            Chunk(content=field.at_cursor, style=CURSOR),
            Chunk(content=field.after_cursor),
        ],
        style=border | border_lightrounded | border_color("amber", 400) | pad_x(1) | text_wrap_none,
        on_input=first(field.on_input, on_enter),
    )


@component
def chat() -> Div:
    conversation, set_conversation = use_state(Conversation(messages=(), draft=""))

    def edit_draft(edit: Callable[[str], str]) -> None:
        set_conversation(lambda c: Conversation(messages=c.messages, draft=edit(c.draft)))

    def send() -> None:
        set_conversation(lambda c: Conversation(messages=(*c.messages, c.draft), draft=""))

    return Div(
        style=col | width(34) | gap(1),
        children=[
            *(
                Text(content=message, style=text_wrap_pretty | text_color("slate", 400))
                for message in conversation.messages
            ),
            composer(conversation.draft, edit_draft, send),
        ],
    )


# --8<-- [end:hook]

# --8<-- [start:widget]


@component
def notes() -> Div:
    text, set_text = use_state("")
    return Div(
        style=col | width(30),
        children=[
            text_area(text, set_text, placeholder="Notes", enter_inserts_newline=True, auto_focus=True),
        ],
    )


# --8<-- [end:widget]


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


CTRL_J = KeyPressed(key=Key.ControlJ)
ENTER = KeyPressed(key=Key.Enter)
DRAFT = (*typed("Rows wrap to fit the box as you type"), CTRL_J, *typed("and Ctrl+J starts a line"))

SCREENSHOTS = [
    ScreenshotSpec(chat(), "text-area-chat-draft", (34, 7), events=DRAFT),
    ScreenshotSpec(chat(), "text-area-chat-sent", (34, 8), events=(*DRAFT, ENTER)),
    ScreenshotSpec(notes(), "text-area-notes", (30, 4)),
    ScreenshotSpec(
        notes(),
        "text-area-notes-filled",
        (30, 6),
        events=(*typed("Milk"), ENTER, *typed("Eggs"), ENTER, *typed("Flour")),
    ),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (chat, notes)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else chat()))
