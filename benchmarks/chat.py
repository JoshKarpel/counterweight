"""
A coding agent's session drawn inline, as Claude Code draws one: the reply streams as Markdown into a region
above a spinner and a prompt, and when it finishes, it and the tool calls after it are printed above the region,
into the scrollback, and the next reply starts streaming into a region that's shrunk back to the prompt.

The replies are `agent-markdown`'s, so most are a sentence or two and about one in seven a summary,
whose region grows a few words a frame and can outgrow the terminal, when the reply scrolls to stay on its end.
So this measures a region whose height changes most frames, and printing a few large, rendered blocks now and then,
on top of feeding all of it to the emulator an inline app keeps of its terminal.
"""

import random
from dataclasses import dataclass
from dataclasses import replace

from benchmarks.agent import prompt
from benchmarks.agent import spinner
from benchmarks.agent_markdown import TOOL_CALLS
from benchmarks.agent_markdown import Message
from benchmarks.agent_markdown import chunk_source
from benchmarks.agent_markdown import render_message
from benchmarks.agent_markdown import split_words
from benchmarks.agent_markdown import tool_call
from benchmarks.harness import Workload
from counterweight import Inline
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.markdown import markdown
from counterweight.styles.utilities import col
from counterweight.styles.utilities import min_height
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import pad_top
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import stick_to_end_y

WORDS_PER_FRAME = 3


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    streaming: Message
    pending: tuple[str, ...]
    """The streaming reply's source still to come, word by word, each with the whitespace after it."""
    finished: tuple[Message, ...]
    """The reply and tool calls the step to this model finished, which it prints."""
    next_id: int


def initial() -> Model:
    return Model(
        tick=0,
        streaming=Message(id=0, kind="assistant", title="", body=""),
        pending=split_words(chunk_source(random.Random(0))),
        finished=(),
        next_id=1,
    )


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    shown, pending = model.pending[:WORDS_PER_FRAME], model.pending[WORDS_PER_FRAME:]
    streaming = replace(model.streaming, body=model.streaming.body + "".join(shown))
    if pending:
        return replace(model, tick=model.tick + 1, streaming=streaming, pending=pending, finished=())
    ids = range(model.next_id, model.next_id + rng.choice(TOOL_CALLS))
    return Model(
        tick=model.tick + 1,
        streaming=Message(id=ids.stop, kind="assistant", title="", body=""),
        pending=split_words(chunk_source(rng)),
        finished=(streaming, *(tool_call(rng, message_id) for message_id in ids)),
        next_id=ids.stop + 1,
    )


def printed(model: Model) -> tuple[AnyElement, ...]:
    return tuple(Div(style=pad_top(1) | pad_x(1), children=(render_message(message),)) for message in model.finished)


def view(model: Model) -> Div:
    # The root shrinks to the terminal's height, and the reply with it, which sticks to its end as it outgrows it.
    return Div(
        style=col | min_height(0),
        children=(
            Div(
                style=col | pad_x(1) | pad_top(1) | overflow_y_scroll | stick_to_end_y,
                children=(markdown(model.streaming.body),),
            ),
            spinner(model.tick),
            prompt(),
        ),
    )


WORKLOAD = Workload(
    name="chat",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(120, 40),
    viewport=Inline(),
    printed=printed,
)
