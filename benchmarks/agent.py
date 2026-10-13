"""
Lots of streaming text: a coding-agent transcript, where the newest message grows by a few words every frame.

Older messages don't change, but each new word reflows the streaming message's wrapped text
and moves everything below it, so this measures wrapping, text measurement and paint
on a screen full of prose, code and diffs.
The transcript is a scroll container holding the newest messages, which the wheel scrolls through in a live run.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import Literal

from benchmarks.harness import Workload
from counterweight.components import Component, component
from counterweight.elements import Chunk, Div, Text
from counterweight.handlers import scroll_on_wheel
from counterweight.styles.styles import CellStyle
from counterweight.styles.utilities import (
    amber_400,
    border,
    border_color,
    border_lightrounded,
    col,
    cyan_400,
    fill,
    green_400,
    justify_children_space_between,
    overflow_y_scroll,
    pad_x,
    red_400,
    row,
    slate_400,
    slate_500,
    text_color,
    text_wrap_stable,
)

WORDS_PER_FRAME = 3
KEPT_MESSAGES = 12

VOCABULARY = (
    "the layout tree component render frame cell style border paint diff text wrap measure width height "
    "function returns value cache hit miss we should probably check whether this test covers that case "
    "first then update call site so nothing else breaks and run suite again before moving on next file "
    "looks like regression came from merge rule where an unset field fell through default instead of left "
    "side I will read module see how it handles empty input and edge cases around zero sized regions"
).split()

FILES = (
    "src/counterweight/layout.py",
    "src/counterweight/paint.py",
    "src/counterweight/styles/styles.py",
    "tests/test_layout.py",
    "src/counterweight/app.py",
)

CODE = (
    "def compute_layout(root: ShadowNode, available: waxy.AvailableSize) -> list[tuple[AnyElement, ResolvedLayout]]:",
    "    tree = waxy.TaffyTree()",
    "    nodes = {id(node): _build_node(tree, node) for node in root.walk()}",
    "    tree.compute_layout(nodes[id(root)], available, measure=_measure_text)",
    "    for node, layout in zip(root.walk(), tree.absolute_layouts(nodes[id(root)])):",
    "        yield node.element, _resolve_layout(layout)",
    "    return [(element, layout) for element, layout in pairs if layout.border.width > 0]",
)

type Kind = Literal["user", "assistant", "read", "edit"]


@dataclass(frozen=True, slots=True)
class Message:
    kind: Kind
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    messages: tuple[Message, ...]
    target_words: int
    tokens: int


def initial() -> Model:
    return Model(
        tick=0,
        messages=(
            Message(kind="user", title="", lines=("Why is the dashboard slower since the merge-rule change?",)),
            Message(kind="assistant", title="", lines=("",)),
        ),
        target_words=60,
        tokens=0,
    )


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    *earlier, streaming = model.messages
    words = " ".join(rng.choice(VOCABULARY) for _ in range(WORDS_PER_FRAME))
    paragraph = f"{streaming.lines[-1]} {words}".strip()
    grown = replace(streaming, lines=(*streaming.lines[:-1], paragraph))
    if rng.random() < 0.05:
        grown = replace(grown, lines=(*grown.lines, ""))

    if len(" ".join(grown.lines).split()) < model.target_words:
        messages = (*earlier, grown)
        target_words = model.target_words
    else:
        messages = (*earlier, grown, tool_call(rng), Message(kind="assistant", title="", lines=("",)))
        target_words = rng.randrange(30, 120)

    return Model(
        tick=model.tick + 1,
        messages=messages[-KEPT_MESSAGES:],
        target_words=target_words,
        tokens=model.tokens + WORDS_PER_FRAME * 4 // 3,
    )


def tool_call(rng: random.Random) -> Message:
    path = rng.choice(FILES)
    start = rng.randrange(len(CODE))
    lines = tuple(CODE[(start + offset) % len(CODE)] for offset in range(rng.randrange(3, 8)))
    if rng.random() < 0.5:
        return Message(kind="read", title=f"Read {path}", lines=lines)
    return Message(kind="edit", title=f"Edit {path}", lines=(f"-{lines[0]}", f"+{lines[0].replace('tree', 'cached')}"))


def view(model: Model, message_component: Callable[[Message], Component]) -> Div:
    return Div(
        style=col,
        children=[
            header(model.tokens),
            Div(
                style=fill(1) | col | pad_x(1) | overflow_y_scroll,
                on_input=scroll_on_wheel(),
                children=[message_component(message) for message in model.messages],
            ),
            spinner(model.tick),
            prompt(),
        ],
    )


@component
def header(tokens: int) -> Div:
    return Div(
        style=row | justify_children_space_between | pad_x(1),
        children=[
            Text(content="agent · ~/projects/counterweight", style=text_color("slate", 400)),
            Text(content=f"{tokens:,} tokens", style=text_color("slate", 500)),
        ],
    )


def render_message(message: Message) -> Div:
    match message.kind:
        case "user":
            return Div(
                children=[Text(content=f"> {message.lines[0]}", style=text_wrap_stable | text_color("cyan", 300))]
            )
        case "assistant":
            return Div(
                style=col,
                children=[Text(content=line or " ", style=text_wrap_stable) for line in message.lines],
            )
        case "read":
            return Div(
                style=col | border | border_lightrounded | border_color("slate", 600),
                children=[
                    Text(content=message.title, style=text_color("amber", 400)),
                    *(Text(content=line, style=text_color("slate", 300)) for line in message.lines),
                ],
            )
        case "edit":
            return Div(
                style=col | border | border_lightrounded | border_color("slate", 600),
                children=[
                    Text(content=message.title, style=text_color("amber", 400)),
                    *(
                        Text(
                            content=line,
                            style=text_color("red", 400) if line.startswith("-") else text_color("green", 400),
                        )
                        for line in message.lines
                    ),
                ],
            )


SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


message_view = component(render_message)
memo_message_view = component(memo=True)(render_message)


@component
def spinner(tick: int) -> Text:
    return Text(
        style=pad_x(1),
        content=[
            Chunk(content=SPINNER[tick % len(SPINNER)], style=CellStyle(foreground=amber_400)),
            Chunk(content=f" Thinking… {tick // 60}s", style=CellStyle(foreground=slate_400)),
            Chunk(content=" · esc to interrupt", style=CellStyle(foreground=slate_500)),
        ],
    )


@component
def prompt() -> Div:
    return Div(
        style=border | border_lightrounded | border_color("slate", 500),
        children=[
            Text(
                content=[
                    Chunk(content="> ", style=CellStyle(foreground=cyan_400)),
                    Chunk(content="Try ", style=CellStyle(foreground=slate_500)),
                    Chunk(content="fix the failing test", style=CellStyle(foreground=green_400)),
                    Chunk(content=" or ", style=CellStyle(foreground=slate_500)),
                    Chunk(content="explain this diff", style=CellStyle(foreground=red_400)),
                ]
            )
        ],
    )


WORKLOAD = Workload(
    name="agent",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=partial(view, message_component=message_view),
    dimensions=(120, 50),
)

MEMO_WORKLOAD = replace(
    WORKLOAD,
    name="agent-memo",
    description="""
`agent`, with each message a `memo` component.

Messages are only appended, and only the newest one grows, so every other message keeps its index and its value:
this measures what reusing all but one message saves.
""",
    view=partial(view, message_component=memo_message_view),
)
