"""
To-do list

A to-do list, the app the quick start builds.

Type a task and press Enter to add it, Tab to move between the tasks, and Space or a click to mark one done.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from functools import partial

from counterweight import app
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
def root() -> Div:
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


# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

ENTER = KeyPressed(key=Key.Enter)
TAB = KeyPressed(key=Key.Tab)
SPACE = KeyPressed(key=Key.Space)

STILLS = [Still("home-quick-start", root(), (44, 12), steps=[*typed("Read the docs"), ENTER, *typed("Ship it")])]

MOVING = AdvanceClock(by=timedelta(milliseconds=500))

DEMOS = [
    Demo(
        "home-quick-start",
        root(),
        (44, 13),
        steps=[
            *paced(
                [*typed("Read the docs"), ENTER, *typed("Ship it"), ENTER],
                pause=AdvanceClock(by=timedelta(milliseconds=90)),
            ),
            MOVING,
            *paced([TAB, TAB, SPACE, TAB, SPACE], pause=MOVING),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
