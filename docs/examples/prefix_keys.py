import asyncio
from dataclasses import dataclass
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.hooks import FocusHandle
from counterweight.hooks import use_focus
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]


@dataclass(frozen=True, slots=True)
class Pane:
    number: int
    handle: FocusHandle


def first_pane() -> tuple[Pane, ...]:
    return (Pane(number=1, handle=FocusHandle()),)


@component
def pane(number: int, handle: FocusHandle, prefix: InputHandler) -> Text:
    focus = use_focus(handle=handle, auto_focus=True)
    typed, set_typed = use_state("")

    def type_key(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=key) if len(key) == 1:
                set_typed(lambda typed: typed + key)
                return ()
            case _:
                return None

    return Text(
        content=f"{number}: {typed}",
        style=fill(1)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if focus.is_focused else border_color("slate", 600)),
        on_input=first(prefix, type_key),
    )


@component
def root() -> Div:
    panes, set_panes = use_state(first_pane)
    is_armed = use_ref(False)
    shows_armed, set_shows_armed = use_state(False)

    def arm(value: bool) -> None:
        is_armed.current = value
        set_shows_armed(value)

    def prefixed(key: str, focused: FocusHandle | None) -> InputResponse:
        match key:
            case "c":
                handle = FocusHandle()
                set_panes(
                    lambda panes: (
                        *panes,
                        Pane(number=max((pane.number for pane in panes), default=0) + 1, handle=handle),
                    )
                )
                return FocusOn(handle)
            case "n":
                return FocusNext()
            case "x":
                set_panes(lambda panes: tuple(pane for pane in panes if pane.handle != focused))
                return FocusNext()
            case _:
                return ()

    def prefix(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlB) if not is_armed.current:
                arm(True)
                return ()
            case KeyPressed(key=key) if is_armed.current:
                arm(False)
                return prefixed(key, receiver.focus_handle)
            case _:
                return None

    return Div(
        style=col | full,
        on_input=prefix,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(pane(p.number, p.handle, prefix).with_key(str(p.number)) for p in panes),
            ),
            Text(
                content=("PREFIX " if shows_armed else "") + "ctrl+b, then c: new pane, n: next pane, x: close pane",
                style=text_color("slate", 900) | text_bg("amber", 400 if shows_armed else 200),
            ),
        ),
    )


# --8<-- [end:example]

TYPED = (KeyPressed(key="h"), KeyPressed(key="i"))
ARMED = (*TYPED, KeyPressed(key=Key.ControlB))
NEW_PANE = (*ARMED, KeyPressed(key="c"), KeyPressed(key="y"), KeyPressed(key="o"))

SCREENSHOTS = [
    ScreenshotSpec(root(), "prefix-keys", (60, 5), events=TYPED),
    ScreenshotSpec(root(), "prefix-keys-armed", (60, 5), events=ARMED),
    ScreenshotSpec(root(), "prefix-keys-new-pane", (60, 5), events=NEW_PANE),
]


CASTS = [
    CastSpec(
        root(),
        "prefix-keys",
        (60, 5),
        steps=paced(
            [
                *NEW_PANE,
                KeyPressed(key=Key.ControlB),
                KeyPressed(key="n"),
                KeyPressed(key="!"),
                KeyPressed(key=Key.ControlB),
                KeyPressed(key="x"),
            ],
            every=timedelta(milliseconds=500),
        ),
    )
]


if __name__ == "__main__":
    asyncio.run(app(root()))
