"""
Typing at the end of a long document, about 110 KB in 1250 lines, inside a scroll container that sticks to its end.

Each frame types one character onto the last line, and starts a new line now and then,
so the document changes every frame while only its last few rows are in view.
`document` draws it as one `Text`, as a pager would draw a file, and `document-lines` as one `Text` per line,
as `markdown` draws one per block; `document-text-area` types into it in a `text_area` instead:
compare them with each other, and before and after a change, to see what drawing content scrolled out of view costs.
"""

import random
from dataclasses import dataclass, replace

from benchmarks.harness import Workload
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import col, fill, overflow_y_scroll, pad_x, stick_to_end_y, text_wrap_stable
from counterweight.widgets import text_area

LINES = 1250
CHARACTERS_PER_LINE = 88

VOCABULARY = (
    "the layout tree component render frame cell style border paint diff text wrap measure width height "
    "function returns value cache hit miss we should probably check whether this test covers that case "
    "first then update call site so nothing else breaks and run suite again before moving on next file"
).split()


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    lines: tuple[str, ...]
    typing: str
    """What's left to type of the next line, a character a frame."""


def line(rng: random.Random) -> str:
    """Words up to a length drawn around `CHARACTERS_PER_LINE`, so some lines wrap at the workload's width and some don't."""
    length = rng.randint(CHARACTERS_PER_LINE // 2, CHARACTERS_PER_LINE * 3 // 2)
    words: list[str] = []
    while length > 0:
        words.append(word := rng.choice(VOCABULARY))
        length -= len(word) + 1
    return " ".join(words)


def initial() -> Model:
    rng = random.Random(0)
    return Model(tick=0, lines=tuple(line(rng) for _ in range(LINES)), typing=line(rng))


def step(model: Model) -> Model:
    *earlier, last = model.lines
    if not model.typing:
        return replace(model, tick=model.tick + 1, lines=(*model.lines, ""), typing=line(random.Random(model.tick)))
    return replace(model, tick=model.tick + 1, lines=(*earlier, last + model.typing[0]), typing=model.typing[1:])


def scroller(*children: Text) -> Div:
    return Div(
        style=col,
        children=(Div(style=fill(1) | col | pad_x(1) | overflow_y_scroll | stick_to_end_y, children=children),),
    )


def one_text(model: Model) -> Div:
    return scroller(Text(content="\n".join(model.lines), style=text_wrap_stable))


def text_per_line(model: Model) -> Div:
    return scroller(*(Text(content=line, style=text_wrap_stable) for line in model.lines))


WORKLOAD = Workload(
    name="document",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=one_text,
    dimensions=(100, 30),
)

LINES_WORKLOAD = replace(
    WORKLOAD,
    name="document-lines",
    description="`document`, drawn as one `Text` per line, so only the last line's `Text` changes each frame.",
    view=text_per_line,
)


@component
def editor(model: Model) -> Div:
    """The document in a `text_area` that fills the screen, which the autopilot types into."""
    draft, set_draft = use_state(lambda: "\n".join(model.lines))
    return Div(style=col | fill(1), children=(text_area(draft, set_draft, style=fill(1), auto_focus=True),))


def in_text_area(model: Model) -> Div:
    return Div(style=col, children=(editor(model),))


TEXT_AREA_WORKLOAD = replace(
    WORKLOAD,
    name="document-text-area",
    description="""
`document` in a `text_area` that fills the screen, which takes one key press a frame at its end, where its cursor starts,
as editing a long document in a text area would.

`use_text_area` wraps the value itself and the widget draws it as three `Text`s:
the rows above the cursor's, the cursor's, and the rows below it.
""",
    view=in_text_area,
    cycled_interjections=tuple(KeyPressed(key=character) for character in "typing at the end of a long document "),
    # The text area inserts any key that's text, so the model steps on one it doesn't edit with, to reach the root.
    step_key=Key.F12,
)
