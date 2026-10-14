"""
`agent`, with someone typing into the prompt, a `text_area` that holds focus, while the transcript streams.

Each frame sends one edit to the prompt before stepping the transcript, in a loop iteration of its own,
as a key press arriving between two streamed chunks would,
so a frame is two iterations: one that edits and re-wraps the prompt, and one that streams, as in `agent`.
The edits type a message a key at a time, fix a typo with Backspace, start lines with Ctrl+J,
paste a test failure, and send it with Enter, which empties the prompt, then start over.
The message wraps onto more rows than the prompt's maximum height, past which it scrolls to keep the cursor in view,
and every row it grows takes one from the transcript above it.
Compare with `agent` to see what a key press costs on a busy screen.
"""

from dataclasses import replace

from benchmarks.agent import WORKLOAD as AGENT
from benchmarks.agent import Model
from benchmarks.agent import header
from benchmarks.agent import message_view
from benchmarks.agent import spinner
from benchmarks.agent import transcript
from counterweight.components import component
from counterweight.elements import Div
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import col
from counterweight.styles.utilities import max_height
from counterweight.widgets import text_area

PROMPT_HEIGHT = 8


def view(model: Model) -> Div:
    return Div(
        style=col,
        children=(
            header(model.tokens),
            # Not focused on mounting, so the prompt is, as in a chat app; Tab still reaches it.
            transcript(model.messages, message_view, auto_focus=False),
            spinner(model.tick),
            prompt(),
        ),
    )


@component
def prompt() -> Div:
    draft, set_draft = use_state("")

    def send(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                set_draft("")
                return ()
            case _:
                return None

    return Div(
        # A column, so the text area stretches across it rather than sizing to its text.
        style=col,
        on_input=send,
        children=(
            text_area(
                draft,
                set_draft,
                placeholder="Try fix the failing test or explain this diff",
                style=max_height(PROMPT_HEIGHT),
                auto_focus=True,
            ),
        ),
    )


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


BACKSPACE = KeyPressed(key=Key.Backspace)
NEWLINE = KeyPressed(key=Key.ControlJ)
SEND = KeyPressed(key=Key.Enter)

FAILURE = """\
tests/test_layout.py:212: in test_text_wraps_at_the_box_edge
\tassert wrap_cells(text, width=40) == expected
E   AssertionError: assert [Row(start=0, end=38), Row(start=38, end=80)] == [Row(start=0, end=40), Row(start=40, end=80)]
E     At index 0 diff: Row(start=0, end=38) != Row(start=0, end=40)
E     Full diff:
E     - [Row(start=0, end=40), Row(start=40, end=80)]
E     + [Row(start=0, end=38), Row(start=38, end=80)]"""

MESSAGE: tuple[KeyPressed | Pasted, ...] = (
    *typed(
        "Before you go further, check whether the wrapping change also broke the box edge case, "
        "since the layout tests started failing right after teh"
    ),
    *(BACKSPACE,) * 3,
    *typed("the merge and I don't think the cache is the cause."),
    NEWLINE,
    *typed("This is the failure I get:"),
    NEWLINE,
    Pasted(text=FAILURE),
    NEWLINE,
    *typed(
        "If the fix is in wrap_cells itself, please add a test that pins the row boundaries for a width "
        "that lands exactly on a word break, and run the whole suite again before moving on to the next file."
    ),
    SEND,
)

WORKLOAD = replace(
    AGENT,
    name="agent-typing",
    description=__doc__ or "",
    view=view,
    cycled_interjections=MESSAGE,
    # The prompt inserts any key that's text, so the transcript steps on one it doesn't edit with, to reach the root.
    step_key=Key.F12,
)
