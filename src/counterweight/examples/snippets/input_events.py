"""
Input handling: Events

An inspector of every event, how a key travels up the tree, a slider dragged with the mouse, and a shopping list.
"""

import asyncio
import sys
from collections.abc import Callable
from dataclasses import fields

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import Receiver
from counterweight.hooks import Ref
from counterweight.hooks import use_focus
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from counterweight.utils import clamp

# --8<-- [start:inspector]

LINES = 8


def concise(event: InputEvent) -> str:
    """The event's repr, without the fields that hold their defaults, such as modifier keys that weren't held."""
    shown = ", ".join(
        f"{field.name}={value!r}" for field in fields(event) if (value := getattr(event, field.name)) != field.default
    )
    return f"{type(event).__name__}({shown})"


@component
def inspector() -> Div:
    lines, set_lines = use_state(tuple[str, ...]())

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        set_lines(lambda lines: (*lines, concise(event))[-LINES:])
        match event:
            case MouseDown():
                return ()
            case _:
                return None

    return Div(
        style=col | full | border | border_lightrounded | pad_x(1),
        on_input=on_input,
        children=(
            Text(content="Press keys, paste, or use the mouse. Ctrl+C quits.", style=text_color("slate", 400)),
            *(Text(content=line) for line in lines),
        ),
    )


# --8<-- [end:inspector]

# --8<-- [start:routing]

Trace = Callable[[InputEvent, str], None]


def traced(name: str, handles: Callable[[InputEvent], bool], trace: Trace) -> InputHandler:
    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        if not isinstance(event, KeyPressed | MouseDown):
            return None
        is_handled = handles(event)
        trace(event, f"{name} {'handles' if is_handled else 'passes'}")
        return () if is_handled else None

    return on_input


@component
def field(name: str, letter: str, trace: Trace) -> Text:
    focus = use_focus(auto_focus=name == "A")

    return Text(
        content=f"{'▸' if focus.is_focused else ' '} field {name}: {letter}",
        style=border | border_lightrounded | pad_x(1) | text_bg("indigo", 700 if focus.is_focused else 900),
        on_input=traced(f"field {name}", lambda event: event == KeyPressed(key=letter), trace),
    )


def is_character_or_press(event: InputEvent) -> bool:
    return isinstance(event, MouseDown) or (isinstance(event, KeyPressed) and len(event.key) == 1)


@component
def routing() -> Div:
    lines, set_lines = use_state(tuple[str, ...]())
    last_event: Ref[InputEvent | None] = use_ref(None)

    def trace(event: InputEvent, step: str) -> None:
        # Every handler on an event's path receives the same event object, so a new one starts a new line.
        if event is last_event.current:
            set_lines(lambda lines: (*lines[:-1], f"{lines[-1]}, {step}"))
            return
        last_event.current = event
        label = repr(event.key) if isinstance(event, KeyPressed) else "press"
        set_lines(lambda lines: (*lines, f"{label}: {step}")[-LINES:])

    return Div(
        style=col | full | border | border_heavy | pad_x(1),
        on_input=traced("root", is_character_or_press, trace),
        children=(
            Text(content="root: every character, and presses"),
            Div(
                style=col | border | border_light | pad_x(1),
                on_input=traced("panel", lambda event: event == KeyPressed(key="p"), trace),
                children=(
                    Text(content="panel: p"),
                    Div(style=row | gap(2), children=(field("A", "a", trace), field("B", "b", trace))),
                ),
            ),
            *(Text(content=line) for line in lines),
        ),
    )


# --8<-- [end:routing]

# --8<-- [start:slider]

WIDTH = 20


@component
def slider() -> Div:
    volume, set_volume = use_state(5)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=position, button=1) | MouseMoved(absolute=position, button=1):
                set_volume(clamp(0, receiver.relative(position).x, WIDTH - 1))
                return ()
            case _:
                return None

    return Div(
        style=col | full | pad_x(1),
        children=(
            Text(content=f"Volume: {volume}"),
            Text(
                content="━" * volume + "●" + "─" * (WIDTH - 1 - volume),
                style=width(WIDTH) | text_color("indigo", 300),
                on_input=on_input,
            ),
        ),
    )


# --8<-- [end:slider]

# --8<-- [start:selection]

ITEMS = ("apples", "bread", "cheese", "dates")


@component
def shopping_list() -> Div:
    selected, set_selected = use_state(frozenset[str]())

    def row(item: str) -> Text:
        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            match event:
                case MouseDown(button=1, is_control_held=True):
                    set_selected(lambda selected: selected ^ {item})
                    return ()
                case MouseDown(button=1):
                    set_selected(frozenset({item}))
                    return ()
                case _:
                    return None

        is_selected = item in selected
        return Text(
            content=f"{'●' if is_selected else '○'} {item}",
            style=pad_x(1) | (text_bg("indigo", 700) if is_selected else default),
            on_input=on_input,
        )

    return Div(style=col | full, children=tuple(row(item) for item in ITEMS))


# --8<-- [end:selection]


ROOTS = (inspector, routing, slider, shopping_list)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position
from counterweight.keys import Key


def keys(*names: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=name) for name in names)


def press(x: int, y: int, is_control_held: bool = False) -> tuple[MouseDown, MouseUp]:
    position = Position(x, y)
    return (
        MouseDown(absolute=position, button=1, is_control_held=is_control_held),
        MouseUp(absolute=position, button=1, is_control_held=is_control_held),
    )


def drag(start: Position, end: Position, moves: int) -> list[MouseDown | MouseMoved | MouseUp]:
    """A drag from `start` to `end` in `moves` even steps, as a hand moves the mouse."""
    path = [
        Position(start.x + (end.x - start.x) * step // moves, start.y + (end.y - start.y) * step // moves)
        for step in range(1, moves + 1)
    ]
    return [
        MouseDown(absolute=start, button=1),
        *(MouseMoved(absolute=position, button=1) for position in path),
        MouseUp(absolute=end, button=1),
    ]


INSPECTOR = (72, 11)
TYPED_KEYS = keys("a", "é", Key.Enter, Key.ControlJ, Key.Up, Key.F1, Key.ControlS)
ALT_KEYS = keys(Key.AltEnter, "alt+b", "alt+B", Key.ControlAltA, Key.AltUp)
PASTE = (Pasted(text="first line\nsecond line"),)
MOUSE = (
    MouseMoved(absolute=Position(1, 0), button=None),
    MouseDown(absolute=Position(1, 0), button=1),
    MouseMoved(absolute=Position(1, 1), button=1),
    MouseUp(absolute=Position(1, 1), button=1),
    MouseDown(absolute=Position(1, 1), button=3),
    MouseUp(absolute=Position(2, 2), button=3),
    MouseScrolledDown(absolute=Position(2, 2), is_control_held=True),
)

ROUTING = (54, 15)
FIELD_B = (34, 5)
PANEL = (40, 3)
ROUTED_KEYS = keys("a", "p", "x", "b")
ROUTED: tuple[KeyPressed | MouseDown | MouseUp, ...] = (*ROUTED_KEYS, *press(*FIELD_B), *press(*PANEL))

SLIDER = (40, 6)
SLID = drag(Position(4, 1), Position(36, 4), moves=8)

SELECTION = (20, 4)
SELECTED = (*press(3, 1), *press(3, 3, is_control_held=True))

STILLS = [
    Still("input-events-keys", inspector(), INSPECTOR, steps=TYPED_KEYS),
    Still("input-events-alt", inspector(), INSPECTOR, steps=ALT_KEYS),
    Still("input-events-paste", inspector(), INSPECTOR, steps=(*keys("h", "i"), *PASTE)),
    Still("input-events-mouse", inspector(), INSPECTOR, steps=MOUSE),
    Still("input-events-routing", routing(), ROUTING, steps=ROUTED),
    Still("input-events-slider", slider(), SLIDER, steps=SLID),
    Still("input-events-selection", shopping_list(), SELECTION, steps=SELECTED),
]


DEMOS = [
    Demo(
        "input-events-routing",
        routing(),
        ROUTING,
        steps=[
            *paced(ROUTED, pause=AdvanceClock(by=timedelta(milliseconds=900))),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
    Demo(
        "input-events-slider",
        slider(),
        SLIDER,
        steps=[
            *paced(
                [*drag(Position(8, 1), Position(16, 1), moves=4), *drag(Position(16, 1), Position(38, 5), moves=10)],
                pause=AdvanceClock(by=timedelta(milliseconds=80)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
