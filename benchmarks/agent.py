"""
Lots of streaming text: a coding-agent transcript, where the newest message grows by a few words every frame.

Older messages don't change, but each new word reflows the streaming message's wrapped text
and moves everything below it, so this measures wrapping, text measurement and paint
on a screen full of prose, code and diffs.
The transcript is a scroll container holding the newest messages, which sticks to its end as they stream in,
and which the wheel and the keyboard scroll back through in a live run, anchored so what's in view stays put.
There, `[` jumps back to the start of each earlier tool call in turn, and End returns to the end.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from functools import partial
from typing import Literal

from benchmarks.harness import Workload
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollIntoView
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.handlers import first
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.styles import CellStyle
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_lightrounded
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import green_400
from counterweight.styles.utilities import justify_children_space_between
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import red_400
from counterweight.styles.utilities import row
from counterweight.styles.utilities import slate_400
from counterweight.styles.utilities import slate_500
from counterweight.styles.utilities import stick_to_end_y
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_stable

WORDS_PER_FRAME = 3
KEPT_MESSAGES = 12
SCROLLED_BACK_AT = 150
SCROLLED_BACK_ROWS = 20

VOCABULARY = [
    "the",
    "layout",
    "tree",
    "component",
    "render",
    "frame",
    "cell",
    "style",
    "border",
    "paint",
    "diff",
    "text",
    "wrap",
    "measure",
    "width",
    "height",
    "function",
    "returns",
    "value",
    "cache",
    "hit",
    "miss",
    "we",
    "should",
    "probably",
    "check",
    "whether",
    "this",
    "test",
    "covers",
    "that",
    "case",
    "first",
    "then",
    "update",
    "call",
    "site",
    "so",
    "nothing",
    "else",
    "breaks",
    "and",
    "run",
    "suite",
    "again",
    "before",
    "moving",
    "on",
    "next",
    "file",
    "looks",
    "like",
    "regression",
    "came",
    "from",
    "merge",
    "rule",
    "where",
    "an",
    "unset",
    "field",
    "fell",
    "through",
    "default",
    "instead",
    "of",
    "left",
    "side",
    "I",
    "will",
    "read",
    "module",
    "see",
    "how",
    "it",
    "handles",
    "empty",
    "input",
    "and",
    "edge",
    "cases",
    "around",
    "zero",
    "sized",
    "regions",
]

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

TOOL_CALLS: frozenset[Kind] = frozenset({"read", "edit"})


@dataclass(frozen=True, slots=True)
class Message:
    id: int
    kind: Kind
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    messages: tuple[Message, ...]
    target_words: int
    tokens: int
    next_id: int


def initial() -> Model:
    return Model(
        tick=0,
        messages=(
            Message(id=0, kind="user", title="", lines=("Why is the dashboard slower since the merge-rule change?",)),
            Message(id=1, kind="assistant", title="", lines=("",)),
        ),
        target_words=60,
        tokens=0,
        next_id=2,
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
        next_id = model.next_id
    else:
        messages = (
            *earlier,
            grown,
            tool_call(rng, model.next_id),
            Message(id=model.next_id + 1, kind="assistant", title="", lines=("",)),
        )
        target_words = rng.randrange(30, 120)
        next_id = model.next_id + 2

    return Model(
        tick=model.tick + 1,
        messages=messages[-KEPT_MESSAGES:],
        target_words=target_words,
        tokens=model.tokens + WORDS_PER_FRAME * 4 // 3,
        next_id=next_id,
    )


def tool_call(rng: random.Random, message_id: int) -> Message:
    path = rng.choice(FILES)
    start = rng.randrange(len(CODE))
    lines = tuple(CODE[(start + offset) % len(CODE)] for offset in range(rng.randrange(3, 8)))
    if rng.random() < 0.5:
        return Message(id=message_id, kind="read", title=f"Read {path}", lines=lines)
    return Message(
        id=message_id,
        kind="edit",
        title=f"Edit {path}",
        lines=(f"-{lines[0]}", f"+{lines[0].replace('tree', 'cached')}"),
    )


TRANSCRIPT = ElementHandle()


type MessageComponent = Callable[[Message, ElementHandle | None], Component]


def view(model: Model, message_component: MessageComponent) -> Div:
    return Div(
        style=col,
        children=(
            header(model.tokens),
            transcript(model.messages, message_component, auto_focus=True),
            spinner(model.tick),
            prompt(),
        ),
    )


@component
def transcript(messages: tuple[Message, ...], message_component: MessageComponent, auto_focus: bool) -> Div:
    """The newest messages, which take focus on mounting if `auto_focus`, for `scroll_on_keys` in a live run."""
    use_focus(auto_focus=auto_focus)
    no_jump: int | None = None
    jumped_to, set_jumped_to = use_state(no_jump)
    # On the message last jumped to, so ScrollIntoView names it once the render that moves it there is laid out.
    landmark, _ = use_state(ElementHandle)

    def jump(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="["):
                # An update, not a value, so each press in a batch steps back from where the one before it landed.
                set_jumped_to(lambda current: previous_tool_call(messages, current))
                return ScrollIntoView(landmark)
            case KeyPressed(key=Key.End):
                # Start the next jump from the newest tool call again, and let scroll_on_keys scroll to the end.
                set_jumped_to(None)
                return None
            case _:
                return None

    return Div(
        style=fill(1) | col | pad_x(1) | overflow_y_scroll | stick_to_end_y,
        handle=TRANSCRIPT,
        on_input=first(jump, scroll_on_keys(), scroll_on_wheel()),
        # Keyed, so a message keeps its node, which anchoring follows, when older ones drop off the top.
        children=tuple(
            message_component(message, landmark if message.id == jumped_to else None).with_key(str(message.id))
            for message in messages
        ),
    )


def previous_tool_call(messages: tuple[Message, ...], before: int | None) -> int | None:
    """
    The id of the newest tool call in `messages` older than the message with id `before`, or than none if it's `None`,
    or `before` itself if there's no such call, so jumping back from the oldest stays there.
    """
    earlier = [m.id for m in messages if m.kind in TOOL_CALLS and (before is None or m.id < before)]
    return earlier[-1] if earlier else before


@component
def header(tokens: int) -> Div:
    return Div(
        style=row | justify_children_space_between | pad_x(1),
        children=(
            Text(content="agent · ~/projects/counterweight", style=text_color("slate", 400)),
            Text(content=f"{tokens:,} tokens", style=text_color("slate", 500)),
        ),
    )


def render_message(message: Message, handle: ElementHandle | None = None) -> Div:
    match message.kind:
        case "user":
            return Div(
                handle=handle,
                children=(Text(content=f"> {message.lines[0]}", style=text_wrap_stable | text_color("cyan", 300)),),
            )
        case "assistant":
            return Div(
                style=col,
                handle=handle,
                children=tuple(Text(content=line or " ", style=text_wrap_stable) for line in message.lines),
            )
        case "read":
            return Div(
                style=col | border | border_lightrounded | border_color("slate", 600),
                handle=handle,
                children=(
                    Text(content=message.title, style=text_color("amber", 400)),
                    *(Text(content=line, style=text_color("slate", 300)) for line in message.lines),
                ),
            )
        case "edit":
            return Div(
                style=col | border | border_lightrounded | border_color("slate", 600),
                handle=handle,
                children=(
                    Text(content=message.title, style=text_color("amber", 400)),
                    *(
                        Text(
                            content=line,
                            style=text_color("red", 400) if line.startswith("-") else text_color("green", 400),
                        )
                        for line in message.lines
                    ),
                ),
            )


SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


message_view = component(render_message)
memo_message_view = component(memo=True)(render_message)


@component
def spinner(tick: int) -> Text:
    return Text(
        style=pad_x(1),
        content=(
            Chunk(content=SPINNER[tick % len(SPINNER)], style=CellStyle(foreground=amber_400)),
            Chunk(content=f" Thinking… {tick // 60}s", style=CellStyle(foreground=slate_400)),
            Chunk(content=" · esc to interrupt", style=CellStyle(foreground=slate_500)),
        ),
    )


@component
def prompt() -> Div:
    return Div(
        style=border | border_lightrounded | border_color("slate", 500),
        children=(
            Text(
                content=(
                    Chunk(content="> ", style=CellStyle(foreground=cyan_400)),
                    Chunk(content="Try ", style=CellStyle(foreground=slate_500)),
                    Chunk(content="fix the failing test", style=CellStyle(foreground=green_400)),
                    Chunk(content=" or ", style=CellStyle(foreground=slate_500)),
                    Chunk(content="explain this diff", style=CellStyle(foreground=red_400)),
                )
            ),
        ),
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

SCROLLED_WORKLOAD = replace(
    WORKLOAD,
    name="agent-scrolled",
    description=f"""
`agent`, scrolled back {SCROLLED_BACK_ROWS} rows at frame {SCROLLED_BACK_AT}, once the transcript overflows,
so the rest of the run reads back while the newest message streams in below the view
and older messages drop off above it.

This measures picking each frame's scroll anchor and keeping it in place.
""",
    interjections={SCROLLED_BACK_AT: (ScrollBy(TRANSCRIPT, y=-SCROLLED_BACK_ROWS),)},
)
