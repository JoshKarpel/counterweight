from datetime import timedelta

from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# isort: split
# --8<-- [start:example]
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from functools import partial

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from counterweight.widgets import text_input


@dataclass(frozen=True, slots=True)
class Task:
    title: str
    is_done: bool = False


FIRST_TASKS: tuple[Task, ...] = (Task("Install Counterweight", is_done=True), Task("Write a component"))


@component
def todo_list() -> Div:
    tasks, set_tasks = use_state(FIRST_TASKS)
    draft, set_draft = use_state("")

    def add_task(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter) if draft.strip():
                set_tasks(lambda tasks: (*tasks, Task(draft.strip())))
                set_draft("")
                return ()
            case _:
                return None

    def toggle(index: int) -> None:
        set_tasks(
            lambda tasks: tuple(replace(t, is_done=not t.is_done) if i == index else t for i, t in enumerate(tasks))
        )

    left = sum(not task.is_done for task in tasks)
    return Div(
        style=col | width(44),
        on_input=first(add_task, tab_focus),
        children=(
            Div(
                style=col | gap(1) | border | border_lightrounded | border_color("slate", 500) | pad_x(1),
                children=(
                    Text(content=f"To do ({left} left)", style=text_color("amber", 400)),
                    Div(style=col, children=tuple(task_row(task, partial(toggle, i)) for i, task in enumerate(tasks))),
                    text_input(draft, set_draft, placeholder="What needs doing?", auto_focus=True),
                ),
            ),
            Text(
                content="enter: add  ·  tab: move  ·  space: done",
                style=text_justify_center | text_color("slate", 500),
            ),
        ),
    )


@component
def task_row(task: Task, toggle_done: Callable[[], None]) -> Text:
    focus = use_focus()

    def on_space(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                toggle_done()
                return ()
            case _:
                return None

    return Text(
        content=f"{'✓' if task.is_done else '○'} {task.title}",
        style=(text_color("emerald", 400) if task.is_done else text_color("slate", 200))
        | (text_bg("slate", 700) if focus.is_focused else default),
        on_input=first(on_space, on_click(toggle_done)),
    )


if __name__ == "__main__":
    asyncio.run(app(todo_list()))
# --8<-- [end:example]


def typed(text: str) -> list[KeyPressed]:
    return [KeyPressed(key=character) for character in text]


ENTER = KeyPressed(key=Key.Enter)
TAB = KeyPressed(key=Key.Tab)
SPACE = KeyPressed(key=Key.Space)

SCREENSHOTS = [
    ScreenshotSpec(
        todo_list(), "home-quick-start", (44, 12), events=[*typed("Read the docs"), ENTER, *typed("Ship it")]
    )
]

TYPING = timedelta(milliseconds=90)
MOVING = timedelta(milliseconds=500)

CASTS = [
    CastSpec(
        todo_list(),
        "home-quick-start",
        (44, 13),
        steps=[
            *paced([*typed("Read the docs"), ENTER, *typed("Ship it"), ENTER], every=TYPING, hold=MOVING),
            *paced([TAB, TAB, SPACE, TAB, SPACE], every=MOVING),
        ],
    )
]
