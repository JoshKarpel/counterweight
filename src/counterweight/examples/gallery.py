"""
Gallery

Every example that ships with counterweight, in a list beside the one selected, which runs in place.

Up and Down, PageUp and PageDown, Home and End move through the list, as the wheel scrolls it, and a click selects.
Enter runs the selected example beside the list and moves focus into it, so keys and the mouse reach it,
and Ctrl+] brings focus back to the list, leaving the example running until the selection moves.
S shows and hides the example's source,
and C copies the example into the working directory, as `counterweight examples copy` does.
Ctrl+C quits, as it does any app, so an example that quits on its own quits the gallery too.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from counterweight._app import app
from counterweight.components import component
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import ScrollIntoView
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.examples.catalog import Example
from counterweight.examples.catalog import Root
from counterweight.examples.catalog import examples
from counterweight.examples.catalog import shown
from counterweight.examples.catalog import write_copy
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.headless import use_scroll_area
from counterweight.highlighting import code_block
from counterweight.hooks import DuplicateUseFocus
from counterweight.hooks import toggle
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_focus
from counterweight.hooks import use_memo
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *


@dataclass(frozen=True, slots=True)
class Entry:
    """A line of the list that runs something: an example, and one of its roots."""

    example: Example
    root: Root

    @property
    def name(self) -> str:
        return self.example.root_name(self.root)


def entries(catalog: Sequence[Example]) -> tuple[Entry, ...]:
    """A line for each root of each example in `catalog`, in its order."""
    return tuple(Entry(example, root) for example in catalog for root in example.roots)


PAGE = 10
"""How many lines PageUp and PageDown move the selection by."""

HINTS = "enter: run it  ·  ctrl+]: back to the list  ·  s: source  ·  c: copy  ·  ctrl+c: quit"

title = position_absolute | inset_top(-1) | inset_left(1) | clip_to_border | text_color("slate", 400)


@component
def root(only: tuple[str, ...] = ()) -> Div:
    """The gallery of the examples named in `only`, or of every one."""
    lines = use_memo(lambda: entries([example for example in examples() if not only or example.name in only]), (only,))
    selected, set_selected = use_state(0)
    # How many times Enter has run the selected example, so each one focuses it again; 0 while it isn't running.
    enters, set_enters = use_state(0)
    shows_source, set_shows_source = use_state(True)
    notice, set_notice = use_state("")
    list_focus, _ = use_state(FocusHandle)
    frame, _ = use_state(FocusHandle)
    selected_line, _ = use_state(ElementHandle)
    entry = lines[selected]

    def select(index: int) -> ScrollIntoView:
        # Only a selection that moves stops the example running, so Up at the top of the list leaves it running.
        if (moved := min(max(index, 0), len(lines) - 1)) != selected:
            set_selected(moved)
            set_enters(0)
            set_notice("")
        return ScrollIntoView(selected_line, block="nearest")

    def copy() -> None:
        try:
            set_notice(f"Copied {entry.example.name} to {write_copy(entry.example, Path.cwd())}")
        except FileExistsError as e:
            set_notice(f"{e.filename} already exists, so it's left as it is")
        except OSError as e:
            set_notice(f"Couldn't copy {entry.example.name}: {e.strerror}")

    def on_list_key(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Up):
                return select(selected - 1)
            case KeyPressed(key=Key.Down):
                return select(selected + 1)
            case KeyPressed(key=Key.PageUp):
                return select(selected - PAGE)
            case KeyPressed(key=Key.PageDown):
                return select(selected + PAGE)
            case KeyPressed(key=Key.Home):
                return select(0)
            case KeyPressed(key=Key.End):
                return select(len(lines) - 1)
            case KeyPressed(key=Key.Enter):
                set_enters(lambda n: n + 1)
                # The frame mounts in the render this causes, which focuses it then.
                return FocusOn(frame)
            case KeyPressed(key="s"):
                set_shows_source(toggle)
                return ()
            case KeyPressed(key="c"):
                copy()
                return ()
            case _:
                return None

    def choose(index: int) -> InputResponse:
        return select(index), FocusOn(list_focus)

    def back_to_the_list(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlRightBracket):
                return FocusOn(list_focus)
            case _:
                return None

    return Div(
        style=col | full,
        on_input=first(back_to_the_list, tab_focus),
        children=(
            Div(
                style=row | fill(1),
                children=(
                    example_list(lines, selected, selected_line, list_focus, on_list_key, choose),
                    Div(
                        style=col | fill(1),
                        children=(
                            about(entry.example),
                            preview(entry, frame, enters),
                            *((source(entry.example).with_key(entry.example.name),) if shows_source else ()),
                        ),
                    ),
                ),
            ),
            Text(content=notice or HINTS, style=text_wrap_none | text_color("slate", 500)),
        ),
    )


@component
def example_list(
    lines: tuple[Entry, ...],
    selected: int,
    selected_line: ElementHandle,
    handle: FocusHandle,
    on_key: Callable[[InputEvent, Receiver], InputResponse],
    choose: Callable[[int], InputResponse],
) -> Div:
    """The examples' lines, under the section each belongs to, the selected one marked."""
    area = use_scroll_area(handle=handle, auto_focus=True)
    children: list[Text] = []
    for index, entry in enumerate(lines):
        if index == 0 or lines[index - 1].example.section != entry.example.section:
            children.append(Text(content=entry.example.section, style=text_color("amber", 400) | text_bold))
        is_selected = index == selected
        children.append(
            Text(
                content=f"{'▸' if is_selected else ' '} {entry.name}",
                style=text_wrap_none | (text_bg("slate", 700) | text_color("sky", 200) if is_selected else default),
                handle=selected_line if is_selected else None,
                on_input=on_click(partial(choose, index)),
            )
        )
    return Div(
        style=col
        | width(max(len(entry.name) for entry in lines) + 6)
        | border
        | border_lightrounded
        | (border_color("sky", 400) if area.focus.is_focused else border_color("slate", 600)),
        on_input=first(on_key, area.on_input),
        children=(
            Text(content=" Examples ", style=title),
            Div(style=fill(1) | col | pad_x(1) | area.style, handle=area.viewport, children=tuple(children)),
        ),
    )


def paragraphs(text: str) -> list[str]:
    """The paragraphs of a docstring, each joined into one line to wrap, since docstrings break their lines by hand."""
    return [" ".join(paragraph.split()) for paragraph in text.split("\n\n")]


@component
def about(example: Example) -> Div:
    """The example's title, and the first paragraph of its description, which says what it is."""
    return Div(
        style=col | border | border_lightrounded | border_color("slate", 600) | pad_x(1),
        children=(
            Text(content=f" {example.title} ", style=title),
            Text(content=paragraphs(example.description)[0], style=text_wrap_pretty | text_color("slate", 300)),
        ),
    )


@component
def preview(entry: Entry, frame: FocusHandle, enters: int) -> Div:
    """Where the example runs once Enter starts it, keyed by its name, so selecting another unmounts it."""
    area, _ = use_state(ElementHandle)
    return Div(
        style=fill(2) | col | border | border_lightrounded | border_color("slate", 600),
        handle=area,
        children=(
            Text(content=f" {entry.name} ", style=title),
            example_frame(entry.root, frame, area, enters).with_key(entry.name)
            if enters
            else Text(
                # The rest of the description, which for an app says how to use it.
                content="\n\n".join([*paragraphs(entry.example.description)[1:], "Press Enter to run it."]),
                style=text_wrap_pretty | text_color("slate", 500) | pad_x(1),
            ),
        ),
    )


@component
def example_frame(root: Root, handle: FocusHandle, area: ElementHandle, enters: int) -> AnyElement:
    """
    An example's root, run as part of this component rather than as its child, so the element it returns is this one's.
    This component is focusable but out of the focus order, as a document's body is,
    so focused, it gets the keys an example's root takes while nothing is focused in an app of its own,
    and an `auto_focus` component that mounts inside it takes focus from it, as it would from nothing.
    A root that makes itself focusable, as one built on a text input does, is focused instead,
    once it mounts and again each time `enters` counts another Enter, since the `FocusOn` Enter sends names this frame.
    """
    example = root()
    element = example.func(*example.args, **example.kwargs)
    try:
        use_focus(handle=handle, in_focus_order=False)
        is_root_focusable = False
    except DuplicateUseFocus:
        is_root_focusable = True
    send_control = use_controls()

    async def focus_the_root() -> None:
        if is_root_focusable:
            # The root is the first focusable component in the area, being the area's outermost.
            send_control(FocusNext(within=area))

    use_effect(focus_the_root, deps=(enters,))
    return element


@component(memo=True)
def source(example: Example) -> Div:
    """
    The example's source, highlighted, which scrolls with the wheel, and with the keys while it's focused.
    It's `memo`, so moving through the list doesn't read and highlight the file again on every key.
    """
    area = use_scroll_area()
    return Div(
        style=fill(1) | col | border | border_lightrounded | border_color("slate", 600),
        on_input=area.on_input,
        children=(
            Text(content=" Source ", style=title),
            Div(
                style=fill(1) | col | area.style,
                handle=area.viewport,
                children=(code_block(shown(example.source()), "python", style=text_wrap_none | pad_x(1)),),
            ),
        ),
    )


# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

SOME = ("chat", "todo", "box-model", "layout-splitting")
DIMENSIONS = (110, 34)


def keys(*names: str) -> list[KeyPressed]:
    return [KeyPressed(key=name) for name in names]


STILLS = [
    Still(
        "gallery",
        root(only=SOME),
        DIMENSIONS,
        steps=[*keys(Key.Down, Key.Enter), *keys(*"Try the gallery"), *keys(Key.Enter)],
    ),
]

DEMOS = [
    Demo(
        "gallery",
        root(only=SOME),
        DIMENSIONS,
        steps=[
            *paced(
                [
                    *keys(Key.Down, Key.Enter),
                    *keys(*"Try it"),
                    *keys(Key.Enter, Key.ControlRightBracket, Key.Down, Key.Down, Key.Enter, Key.ControlRightBracket),
                    *keys(Key.Down, Key.Down, "s", Key.Enter),
                ],
                pause=AdvanceClock(by=timedelta(milliseconds=400)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
