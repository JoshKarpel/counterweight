"""
A coding agent's transcript in Markdown: short narration between tool calls, and now and then a longer summary,
streamed a few words a frame and rendered with `markdown` and `code_block`.

The shapes come from the assistant text in a set of real Claude Code transcripts (about five thousand text blocks):
most blocks are one short paragraph between a couple of tool calls, mostly shell commands, then edits and reads;
about one in seven is a summary of paragraphs, short bulleted lists, an occasional heading, table or short code block.
Inline code is dense (about one word in twenty), bold is occasional, and links and italics are rare.
Each tuple of sizes below holds that distribution's 10th, 25th, 50th, 75th and 90th percentiles,
drawn from uniformly.

The streaming block's source is cut at a word boundary every frame, so it is often unfinished Markdown,
and is parsed again every frame, while every finished block hits `markdown`'s cache.
"""

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from math import ceil
from typing import Literal

from benchmarks.agent import CODE, FILES, VOCABULARY, header, prompt, spinner
from benchmarks.harness import Workload
from counterweight.components import Component, component
from counterweight.elements import Div, Text
from counterweight.highlighting import code_block
from counterweight.markdown import markdown
from counterweight.styles.utilities import (
    border,
    border_color,
    border_lightrounded,
    col,
    fill,
    gap_height,
    pad_x,
    text_color,
)

WORDS_PER_FRAME = 3
TRANSCRIPT_ROWS = 40
WRAP_WIDTH = 112

SUMMARY_SHARE = 0.15
NARRATION_WORDS = (9, 14, 20, 28, 40)
PARAGRAPH_WORDS = (6, 13, 22, 34, 54)
LIST_ITEMS = (2, 2, 3, 4, 5)
LIST_ITEM_WORDS = (8, 14, 24, 38, 55)
FENCE_LINES = (1, 1, 3, 5, 9)
TABLE_ROWS = (3, 4, 5, 6, 8)
TABLE_COLUMNS = (2, 3, 3, 4, 4)
SUMMARY_BLOCKS = (4, 6, 8, 11, 15)
TOOL_CALLS = (0, 1, 2, 5, 9)

# How often each kind of block follows the first paragraph of a summary, and each word is marked up.
SUMMARY_BLOCK_WEIGHTS = {"paragraph": 55, "bullets": 30, "numbered": 4, "heading": 3, "fence": 3, "table": 3}
CODE_SPAN_SHARE = 0.047
BOLD_SHARE = 0.012
LINK_SHARE = 0.002

LISTS = frozenset({"bullets", "numbered"})
TOOL_WEIGHTS = {"bash": 53, "edit": 28, "read": 19}
FENCE_LANGUAGES = ("python", "python", "text", "bash", "")
CODE_SPANS = (
    "use_state",
    "Text",
    "layout.py",
    "wrap_cells",
    "just test",
    "CellStyle",
    "fill(1)",
    "update_shadow",
    "paint_layout",
    "--frames",
    "None",
    "tests/test_paint.py",
)
COMMANDS = (
    ("just test -k layout", ("tests pass", "coverage: 100%")),
    ("git status --short", (" M src/counterweight/layout.py", " M tests/test_layout.py")),
    ("rg -n 'def wrap_cells' src", ("src/counterweight/layout.py:212:def wrap_cells(",)),
    ("uv run mypy", ("Success: no issues found in 96 source files",)),
)

type Kind = Literal["user", "assistant", "read", "edit", "bash"]


@dataclass(frozen=True, slots=True)
class Message:
    kind: Kind
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    messages: tuple[Message, ...]
    pending: tuple[str, ...]
    """The streaming message's source still to come, word by word, each with the whitespace after it."""
    tokens: int


def initial() -> Model:
    words = split_words(chunk_source(random.Random(0)))
    return Model(
        tick=0,
        messages=(
            Message(kind="user", title="", body="Why is the dashboard slower since the merge-rule change?"),
            Message(kind="assistant", title="", body=""),
        ),
        pending=words,
        tokens=0,
    )


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    *earlier, streaming = model.messages
    shown, pending = model.pending[:WORDS_PER_FRAME], model.pending[WORDS_PER_FRAME:]
    messages = (*earlier, replace(streaming, body=streaming.body + "".join(shown)))
    if not pending:
        tools = tuple(tool_call(rng) for _ in range(rng.choice(TOOL_CALLS)))
        messages = (*messages, *tools, Message(kind="assistant", title="", body=""))
        pending = split_words(chunk_source(rng))
    return Model(
        tick=model.tick + 1,
        messages=visible(messages),
        pending=pending,
        tokens=model.tokens + WORDS_PER_FRAME * 4 // 3,
    )


def split_words(source: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\S+\s*", source))


def chunk_source(rng: random.Random) -> str:
    """One block of an agent's text: usually a sentence or two of narration, sometimes a summary."""
    if rng.random() >= SUMMARY_SHARE:
        return prose(rng, rng.choice(NARRATION_WORDS))
    kinds, weights = zip(*SUMMARY_BLOCK_WEIGHTS.items())
    chosen = ["paragraph", *rng.choices(kinds, weights, k=rng.choice(SUMMARY_BLOCKS) - 1)]
    # Two lists in a row would merge into one loose list, which agents rarely write, so the second becomes prose.
    kinds_in_order = [
        "paragraph" if kind in LISTS and previous in LISTS else kind for previous, kind in zip(["", *chosen], chosen)
    ]
    return "\n\n".join(summary_block(rng, kind) for kind in kinds_in_order)


def summary_block(rng: random.Random, kind: str) -> str:
    match kind:
        case "paragraph":
            return prose(rng, rng.choice(PARAGRAPH_WORDS))
        case "bullets" | "numbered":
            items = [prose(rng, rng.choice(LIST_ITEM_WORDS)) for _ in range(rng.choice(LIST_ITEMS))]
            return "\n".join(f"{'-' if kind == 'bullets' else f'{n}.'} {item}" for n, item in enumerate(items, 1))
        case "heading":
            return f"## {prose(rng, rng.randrange(2, 5)).capitalize()}"
        case "fence":
            start = rng.randrange(len(CODE))
            lines = [CODE[(start + n) % len(CODE)] for n in range(rng.choice(FENCE_LINES))]
            return "\n".join([f"```{rng.choice(FENCE_LANGUAGES)}", *lines, "```"])
        case _:
            columns = rng.choice(TABLE_COLUMNS)
            rows = [[prose(rng, rng.randrange(1, 4)) for _ in range(columns)] for _ in range(rng.choice(TABLE_ROWS))]
            header_row, *body = rows
            return "\n".join(
                [
                    f"| {' | '.join(header_row)} |",
                    f"|{'---|' * columns}",
                    *(f"| {' | '.join(cells)} |" for cells in body),
                ]
            )


def prose(rng: random.Random, words: int) -> str:
    """`words` words of agent prose, with inline code, bold and links as often as the transcripts have them."""
    out = []
    for _ in range(words):
        roll = rng.random()
        if roll < CODE_SPAN_SHARE:
            out.append(f"`{rng.choice(CODE_SPANS)}`")
        elif roll < CODE_SPAN_SHARE + BOLD_SHARE:
            out.append(f"**{rng.choice(VOCABULARY)}**")
        elif roll < CODE_SPAN_SHARE + BOLD_SHARE + LINK_SHARE:
            out.append(f"[{rng.choice(VOCABULARY)}](https://www.counterweight.dev/)")
        else:
            out.append(rng.choice(VOCABULARY))
    return " ".join(out)


def tool_call(rng: random.Random) -> Message:
    kinds, weights = zip(*TOOL_WEIGHTS.items())
    kind: Kind = rng.choices(kinds, weights)[0]
    match kind:
        case "bash":
            command, output = rng.choice(COMMANDS)
            return Message(kind="bash", title=f"$ {command}", body="\n".join(output))
        case "read":
            start = rng.randrange(len(CODE))
            lines = (CODE[(start + n) % len(CODE)] for n in range(rng.randrange(3, 8)))
            return Message(kind="read", title=f"Read {rng.choice(FILES)}", body="\n".join(lines))
        case _:
            line = rng.choice(CODE)
            return Message(
                kind="edit", title=f"Edit {rng.choice(FILES)}", body=f"-{line}\n+{line.replace('tree', 'cached')}"
            )


def estimated_rows(message: Message) -> int:
    """
    About how many rows `message` takes: each source line wrapped, a table row and its rule, and a box's border.
    There's no scrolling yet, so older messages fall off the top as the transcript grows.
    """
    rows = sum(
        (2 if line.startswith("|") else max(1, ceil(len(line) / WRAP_WIDTH))) for line in message.body.split("\n")
    )
    return rows + (2 if message.kind in ("read", "edit", "bash") else 0) + 1


def visible(messages: tuple[Message, ...]) -> tuple[Message, ...]:
    """The newest messages that fit in the transcript, by `estimated_rows`."""
    kept: list[Message] = []
    rows = 0
    for message in reversed(messages):
        rows += estimated_rows(message)
        if rows > TRANSCRIPT_ROWS and kept:
            break
        kept.append(message)
    return tuple(reversed(kept))


def view(model: Model, message_component: Callable[[Message], Component]) -> Div:
    return Div(
        style=col,
        children=(
            header(model.tokens),
            Div(
                style=fill(1) | col | gap_height(1) | pad_x(1),
                children=tuple(message_component(message) for message in model.messages),
            ),
            spinner(model.tick),
            prompt(),
        ),
    )


def render_message(message: Message) -> Div:
    match message.kind:
        case "user":
            return Div(children=(Text(content=f"> {message.body}", style=text_color("cyan", 300)),))
        case "assistant":
            return markdown(message.body)
        case "bash":
            body = Text(content=message.body, style=text_color("slate", 400))
        case "read":
            body = code_block(message.body, "python")
        case "edit":
            body = code_block(message.body, "diff")
    return Div(
        style=col | border | border_lightrounded | border_color("slate", 600),
        children=(Text(content=message.title, style=text_color("amber", 400)), body),
    )


message_view = component(render_message)
memo_message_view = component(memo=True)(render_message)

WORKLOAD = Workload(
    name="agent-markdown",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=partial(view, message_component=message_view),
    dimensions=(120, 50),
)

MEMO_WORKLOAD = replace(
    WORKLOAD,
    name="agent-markdown-memo",
    description="`agent-markdown`, with each message a `memo` component.",
    view=partial(view, message_component=memo_message_view),
)
