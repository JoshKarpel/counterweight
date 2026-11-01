"""
Chat

A chat with a canned bot, whose replies are Markdown that streams in a word at a time.

Type in the prompt at the bottom: Enter sends, and Alt+Enter or Ctrl+J starts a new line.
The prompt takes PageUp and PageDown to move its cursor,
so Shift+PageUp and Shift+PageDown scroll the transcript from it, as do Ctrl+Up and Ctrl+Down,
for terminals that keep Shift+PageUp for their own scrollback, and so does the wheel.
Tab moves focus between the prompt and the transcript, as does a click on either,
and while the transcript is focused, the arrows, PageUp, PageDown, Home and End scroll it.
Escape stops a reply that's still arriving.
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from functools import partial
from typing import Literal

from counterweight import app
from counterweight.components import component
from counterweight.controls import ScrollTo
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import page_down
from counterweight.handlers import page_up
from counterweight.handlers import tab_focus
from counterweight.headless import use_scroll_area
from counterweight.hooks import use_clock
from counterweight.hooks import use_effect
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown
from counterweight.styles.utilities import *
from counterweight.widgets import TextFieldStyles
from counterweight.widgets import text_area

REPLIES = (
    """\
Reverse a list in place with `reverse`, or get a reversed copy with a slice:

```python
peaks = ["Everest", "K2", "Kangchenjunga", "Lhotse", "Makalu", "Cho Oyu", "Dhaulagiri", "Manaslu"]
peaks.reverse()  # in place, returns None
descending = sorted(peaks, key=lambda peak: HEIGHTS[peak], reverse=True)  # a new list, tallest first
```

Which to pick:

- `reverse()` when you don't need the original order again
- `peaks[::-1]` for a reversed copy
- `reversed(peaks)` to loop backwards without copying
""",
    """\
Here's how the common sorts compare:

| Algorithm      | Best       | Worst      | Stable |
|:---------------|:----------:|:----------:|:------:|
| Insertion sort | n          | n²         | yes    |
| Merge sort     | n log n    | n log n    | yes    |
| Quicksort      | n log n    | n²         | no     |
| Timsort        | n          | n log n    | yes    |

Python's `sorted` is **Timsort**, so it's stable:
items that compare equal keep their order, which lets you sort by several keys in turn.
""",
    """\
To find the biggest files under a directory:

```bash
find . -type f -not -path "./.git/*" -exec du -h {} + 2>/dev/null | sort --human-numeric-sort --reverse | head -n 10
```

1. `find` lists every file, skipping `.git`
2. `du -h` measures each one
3. `sort` puts the largest first, and `head` keeps ten

> [!TIP]
> Code wider than the transcript scrolls sideways with a trackpad's sideways swipe or a tilting wheel.
""",
)

WORD_DELAY = timedelta(milliseconds=30)
"""How long the bot takes to type each word of its reply."""

type Author = Literal["you", "bot"]


@dataclass(frozen=True, slots=True)
class Message:
    author: Author
    text: str


@dataclass(frozen=True, slots=True)
class Reply:
    """The reply the bot is typing, a word at a time, each word with the whitespace before it."""

    words: tuple[str, ...]
    is_stopped: bool = False

    @classmethod
    def to(cls, messages: tuple[Message, ...]) -> Reply:
        """The next canned reply, which a real chat would ask a model for."""
        asked = sum(message.author == "you" for message in messages)
        return cls(words=tuple(re.findall(r"\s*\S+", REPLIES[(asked - 1) % len(REPLIES)])))


@dataclass(frozen=True, slots=True)
class Chat:
    messages: tuple[Message, ...]
    draft: str
    reply: Reply | None

    def sent(self) -> Chat:
        """The draft sent, and a reply started, unless the draft is blank or the bot is still replying."""
        if self.reply is not None or not self.draft.strip():
            return self
        messages = (*self.messages, Message("you", self.draft))
        return Chat(messages=messages, draft="", reply=Reply.to(messages))

    def stopped(self) -> Chat:
        """The reply stopped where it's got to, which `replied` then adds to the messages."""
        return self if self.reply is None else replace(self, reply=replace(self.reply, is_stopped=True))

    def replied(self, text: str) -> Chat:
        """The reply, as far as it got, added to the messages."""
        return Chat(messages=(*self.messages, Message("bot", text)), draft=self.draft, reply=None)


@component
def root() -> Div:
    chat, set_chat = use_state(Chat(messages=(), draft="", reply=None))
    transcript, _ = use_state(ElementHandle)
    scroll = use_scroll(transcript)
    is_replying = chat.reply is not None

    def finish_reply(text: str) -> None:
        set_chat(partial(Chat.replied, text=text))

    def edit_draft(edit: Callable[[str], str]) -> str:
        return set_chat(lambda c: replace(c, draft=edit(c.draft))).draft

    def on_key(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            # Enter bubbles out of the prompt, which only inserts a line break for Alt+Enter or Ctrl+J.
            case KeyPressed(key=Key.Enter):
                set_chat(Chat.sent)
                # A y past the end scrolls to the end of the content with the new message in it.
                return ScrollTo(transcript, y=sys.maxsize)
            case KeyPressed(key=Key.Escape) if is_replying:
                set_chat(Chat.stopped)
                return ()
            case KeyPressed(key=Key.ShiftPageUp | Key.ControlUp):
                return page_up(transcript, scroll)
            case KeyPressed(key=Key.ShiftPageDown | Key.ControlDown):
                return page_down(transcript, scroll)
            case _:
                return None

    return Div(
        style=col | full | pad_x(1),
        on_input=first(on_key, tab_focus),
        children=(
            transcript_pane(chat.messages, chat.reply, finish_reply, transcript),
            text_area(
                chat.draft,
                edit_draft,
                placeholder="Message the bot",
                # Three rows of text between its top and bottom borders, past which it scrolls.
                style=max_height(5),
                styles=TextFieldStyles(focused_box=border_color("sky", 400)),
                auto_focus=True,
            ),
            Text(
                content=("esc: stop the reply" if is_replying else "enter: send  ·  alt+enter: new line")
                + "  ·  shift+pgup/pgdn or ctrl+↑/↓: scroll  ·  tab: transcript",
                style=text_justify_center | text_wrap_pretty | text_color("slate", 500),
            ),
        ),
    )


@component
def transcript_pane(
    messages: tuple[Message, ...], reply: Reply | None, finish_reply: Callable[[str], None], transcript: ElementHandle
) -> Div:
    """
    The messages, and the reply the bot is typing, scrolled by the keys while the pane is focused
    and by the wheel anywhere over it, and kept scrolled to the newest as the reply streams in.
    The root passes the transcript's element handle, so the prompt's keys can scroll it too.
    """
    area = use_scroll_area(stick_to_end=True, viewport=transcript)
    return Div(
        # Padded below, so the messages' bars don't touch the prompt's border, which border healing would join.
        style=fill(1) | col | pad_bottom(1),
        on_input=area.on_input,
        children=(
            Div(
                style=fill(1) | col | gap(1) | area.style,
                handle=area.viewport,
                children=(
                    *(chat_message(m) for m in messages),
                    *((typing_reply(reply, finish_reply),) if reply is not None else ()),
                ),
            ),
            # Siblings of the transcript, so they stay put as it scrolls.
            *(
                (
                    Text(
                        content="─" * 3 + " pgup/pgdn: scroll  ·  tab: back to the prompt ",
                        style=position_absolute | inset_bottom(0) | inset_left(0) | text_color("sky", 400),
                    ),
                )
                if area.focus.is_focused
                else ()
            ),
            *(
                (
                    Text(
                        content=" ↓ jump to latest ",
                        style=position_absolute
                        | inset_bottom(0)
                        | inset_right(0)
                        | text_bg("sky", 800)
                        | text_color("sky", 100),
                        on_input=on_click(lambda: area.to_end),
                    ),
                )
                if not area.is_at_end
                else ()
            ),
        ),
    )


@component
def typing_reply(reply: Reply, finish: Callable[[str], None]) -> Div:
    """
    The bot's reply, as many words of it as have had time to arrive since it began,
    which `finish` adds to the messages once all of it has, or once it's stopped.
    The clock decides how far it's got, so an autopilot's `AdvanceClock` moves it on, as time does.
    """
    shown = min(use_clock(WORD_DELAY).since_mount // WORD_DELAY, len(reply.words))
    text = "".join(reply.words[:shown])
    is_done = reply.is_stopped or shown == len(reply.words)

    async def finish_when_done() -> None:
        if is_done:
            finish(text)

    use_effect(finish_when_done, deps=(is_done,))
    return message_box(Message("bot", text))


AUTHOR_COLORS: dict[Author, ColorName] = {"you": "amber", "bot": "sky"}


@component(memo=True)
def chat_message(message: Message) -> Div:
    """One message, which is `memo`, so while a reply streams in, the messages before it don't render again."""
    return message_box(message)


def message_box(message: Message) -> Div:
    """
    A message under its author's name, rendered as Markdown,
    keeping the line breaks in yours, as chat apps do, rather than joining the lines you broke with Alt+Enter or Ctrl+J.
    """
    color = AUTHOR_COLORS[message.author]
    return Div(
        style=col | border_light | border_left | border_color(color, 400) | pad_left(1),
        children=(
            Text(content=message.author, style=text_color(color, 300) | text_bold),
            markdown(message.text, keeps_line_breaks=message.author != "bot"),
        ),
    )


# --8<-- [start:scenes]


from counterweight.autopilot import advance
from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.events import Pasted
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

PAUSE = AdvanceClock(by=timedelta(milliseconds=60))

ENTER = KeyPressed(key=Key.Enter)


STILLS = [
    Still(
        "chat",
        root(),
        (100, 30),
        steps=[
            Pasted(text="How do I reverse a list?"),
            ENTER,
            AdvanceClock(by=timedelta(seconds=5)),
            Pasted(text="Which sort should I use?"),
            ENTER,
            AdvanceClock(by=timedelta(seconds=5)),
        ],
    ),
]

DEMOS = [
    Demo(
        "chat",
        root(),
        (80, 24),
        steps=[
            *paced(typed("How do I reverse a list?"), pause=PAUSE),
            AdvanceClock(by=timedelta(milliseconds=300)),
            ENTER,
            *advance(timedelta(seconds=3), step=WORD_DELAY),
            *paced(typed("Which sort should I use?"), pause=PAUSE),
            AdvanceClock(by=timedelta(milliseconds=300)),
            ENTER,
            *advance(timedelta(seconds=1), step=WORD_DELAY),
            KeyPressed(key=Key.Escape),
            AdvanceClock(by=timedelta(seconds=3)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
