"""
A fuzzy picker over five thousand paths, typed into faster than it renders:
each frame's keys arrive in one burst, which the loop handles in one batch before it renders once,
as keys typed ahead of a slow frame, or before the first one, do.

Each burst erases the last frame's query with Backspace, types the next one a key at a time,
and moves the highlight down a few rows, so every key runs the picker's handler against state no render has shown:
an edit goes to the text field, and a move decides from the latest text, matching it again in the handler.
Compare with `picker` to see what a frame of typed-ahead keys costs beside a frame of one change.
"""

from dataclasses import dataclass

from benchmarks.harness import Workload
from benchmarks.picker import PATHS
from benchmarks.picker import QUERY
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.headless import Highlight
from counterweight.headless import fuzzy_matches
from counterweight.headless import use_text_input
from counterweight.hooks import Setter
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import col
from counterweight.styles.utilities import slate_300
from counterweight.styles.utilities import slate_800
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_none

SHOWN = 15
MOVES = 3


def latest[T](set_state: Setter[T]) -> T:
    """The state as the updates since the last render left it, read through its setter, which applies an updater at once."""
    seen: list[T] = []

    def read(value: T) -> T:
        seen.append(value)
        return value

    set_state(read)
    return seen[0]


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    query: str
    erased: int
    """How long the query the burst erases is: the last frame's."""


def initial() -> Model:
    return Model(tick=0, query="", erased=0)


def step(model: Model) -> Model:
    tick = model.tick + 1
    return Model(tick=tick, query=QUERY[: 1 + tick % len(QUERY)], erased=len(model.query))


def burst(model: Model) -> tuple[AnyEvent, ...]:
    return (
        *(KeyPressed(key=Key.Backspace) for _ in range(model.erased)),
        *(KeyPressed(key=char) for char in model.query),
        *(KeyPressed(key=Key.Down) for _ in range(model.tick % MOVES + 1)),
    )


def shown_for(text: str) -> tuple[str, ...]:
    return fuzzy_matches(text, PATHS)[:SHOWN]


@component
def picker() -> Div:
    text, set_text = use_state("")
    highlight, set_highlight = use_state(Highlight())
    field = use_text_input(text, set_text, auto_focus=True)
    shown = shown_for(text)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        before = latest(set_text)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                now_shown = shown_for(before)
                if not now_shown:
                    return None
                set_highlight(latest(set_highlight).moved(now_shown, 1 if key == Key.Down else -1))
                return ()
            case _:
                response = field.on_input(event, receiver)
                if latest(set_text) != before:
                    set_highlight(Highlight())
                return response

    index = highlight.index_in(shown)
    return Div(
        style=col,
        on_input=on_input,
        children=(
            Text(content=f"> {field.before_cursor}{field.at_cursor}{field.after_cursor}", style=text_wrap_none),
            *(
                Text(
                    content=path,
                    style=text_wrap_none | (text_bg(slate_800) if row == index else text_color(slate_300)),
                )
                for row, path in enumerate(shown)
            ),
        ),
    )


def view(model: Model) -> Div:
    return Div(style=col, children=(picker(),))


WORKLOAD = Workload(
    name="picker-burst",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(100, 20),
    step_key=Key.F5,
    burst=burst,
)
