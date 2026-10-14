"""
A chat with a canned bot, whose replies are Markdown that streams in a word at a time.

Run it with `uv run python -m examples.chat`.
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
from collections.abc import AsyncIterator
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from functools import partial
from typing import Literal

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ScrollTo
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import page_down
from counterweight.handlers import page_up
from counterweight.handlers import tab_focus
from counterweight.headless import use_scroll_area
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown
from counterweight.styles import CellStyle
from counterweight.styles import Style
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

type Author = Literal["you", "bot"]


@dataclass(frozen=True, slots=True)
class Message:
    author: Author
    text: str


@dataclass(frozen=True, slots=True)
class Chat:
    messages: tuple[Message, ...]
    draft: str
    reply: str | None
    """The bot's reply so far, while it's arriving."""

    def sent(self) -> Chat:
        """The draft sent, and a reply started, unless the draft is blank or the bot is still replying."""
        if self.reply is not None or not self.draft.strip():
            return self
        return Chat(messages=(*self.messages, Message("you", self.draft)), draft="", reply="")

    def streamed(self, chunk: str) -> Chat:
        """`chunk` added to the reply, unless the reply was stopped before the chunk arrived."""
        return self if self.reply is None else replace(self, reply=self.reply + chunk)

    def replied(self) -> Chat:
        """The reply so far added to the messages, which is the whole reply unless it was stopped early."""
        if self.reply is None:
            return self
        return Chat(messages=(*self.messages, Message("bot", self.reply)), draft=self.draft, reply=None)


async def stream_reply(messages: tuple[Message, ...]) -> AsyncIterator[str]:
    """
    A stand-in for a model's streaming API: the next canned reply, a word at a time,
    each with the whitespace before it, so its line breaks arrive as they would.
    """
    asked = sum(message.author == "you" for message in messages)
    for chunk in re.findall(r"\s*\S+", REPLIES[(asked - 1) % len(REPLIES)]):
        await asyncio.sleep(WORD_DELAY.total_seconds())
        yield chunk


@component
def root() -> Div:
    chat, set_chat = use_state(Chat(messages=(), draft="", reply=None))
    transcript, _ = use_state(ElementHandle)
    scroll = use_scroll(transcript)
    is_replying = chat.reply is not None

    async def reply() -> None:
        if not is_replying:
            return
        async for chunk in stream_reply(chat.messages):
            set_chat(partial(Chat.streamed, chunk=chunk))
        set_chat(Chat.replied)

    # Changing deps cancels the effect, so stopping a reply early stops its stream.
    use_effect(reply, deps=(is_replying,))

    def edit_draft(edit: Callable[[str], str]) -> None:
        set_chat(lambda c: replace(c, draft=edit(c.draft)))

    def on_key(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            # Enter bubbles out of the prompt, which only inserts a line break for Alt+Enter or Ctrl+J.
            case KeyPressed(key=Key.Enter):
                set_chat(Chat.sent)
                # A y past the end scrolls to the end of the content with the new message in it.
                return ScrollTo(transcript, y=sys.maxsize)
            case KeyPressed(key=Key.Escape) if is_replying:
                set_chat(Chat.replied)
                return ()
            case KeyPressed(key=Key.ShiftPageUp | Key.ControlUp):
                return page_up(transcript, scroll)
            case KeyPressed(key=Key.ShiftPageDown | Key.ControlDown):
                return page_down(transcript, scroll)
            case _:
                return None

    messages = (*chat.messages, *((Message("bot", chat.reply),) if chat.reply is not None else ()))
    return Div(
        style=col | full | pad_x(1),
        on_input=first(on_key, tab_focus),
        children=(
            transcript_pane(messages, transcript),
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
def transcript_pane(messages: tuple[Message, ...], transcript: ElementHandle) -> Div:
    """
    The messages, scrolled by the keys while the pane is focused and by the wheel anywhere over it,
    and kept scrolled to the newest as replies stream in.
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
                children=tuple(chat_message(m) for m in messages),
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


AUTHOR_COLORS: dict[Author, ColorName] = {"you": "amber", "bot": "sky"}


@component(memo=True)
def chat_message(message: Message) -> Div:
    """
    One message, under its author's name, rendered as Markdown,
    keeping the line breaks in yours, as chat apps do, rather than joining the lines you broke with Alt+Enter or Ctrl+J.
    It's `memo`, so while a reply streams in, the messages before it don't render again.
    """
    color = AUTHOR_COLORS[message.author]
    return Div(
        style=col | border_light | border_left | border_color(color, 400) | pad_left(1),
        children=(
            Text(content=message.author, style=text_color(color, 300) | Style(text_style=CellStyle(bold=True))),
            markdown(message.text, keeps_line_breaks=message.author != "bot"),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
