"""
Headless components: Pickers

A combobox, a command palette, a search box, Tab cycling, inline completion, rows that refresh, marks, headings,
a preview, and the combobox widget, each built from the same parts.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from functools import partial

from counterweight import app
from counterweight.components import component
from counterweight.controls import ScrollIntoView
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.events import response_controls
from counterweight.focus import ElementHandle
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.headless import Highlight
from counterweight.headless import TextInput
from counterweight.headless import prefix_matches
from counterweight.headless import subsequence_matches
from counterweight.headless import substring_matches
from counterweight.headless import use_text_input
from counterweight.hooks import Setter
from counterweight.hooks import get_state
from counterweight.hooks import use_clock
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *
from counterweight.widgets import combobox
from counterweight.widgets import text_input

PACKAGES = ("counterweight", "hypothesis", "mypy", "pydantic", "pydantic-settings", "pytest", "pytest-asyncio", "ruff")
COMMANDS = ("Close tab", "Copy path", "Find in files", "Format document", "Open file", "Reload window", "Split right")
QUERIES = ("python asyncio", "python dataclasses", "python pathlib", "rust lifetimes", "rust traits")
PROGRAMS = ("cargo", "cat", "cd", "chmod", "chown", "git", "grep", "gzip")
HISTORY = ("git status", "git switch main", "git commit -m 'Add pickers'", "just test", "just docs-serve")

# --8<-- [start:shared]

CURSOR = Style(text_style=(text_color("slate", 900) | text_bg("sky", 300)).text_style)


@dataclass(frozen=True, slots=True)
class Query:
    """The text typed into a picker that owns it, and the highlight, which an edit puts back on the first match."""

    text: str = ""
    highlight: Highlight = Highlight()

    def edited(self, text: str) -> Query:
        return self if text == self.text else Query(text=text)


def field_row(field: TextInput, ghost: str = "") -> Div:
    """The text and its cursor, as `text_input` draws them, and `ghost` dimmed after them, starting in the cursor's cell."""
    at_cursor = field.at_cursor
    if ghost and not field.after_cursor:
        at_cursor, ghost = ghost[0], ghost[1:]
    return Div(
        style=row | overflow_x_scroll | stick_to_end_x,
        on_input=field.on_press,
        children=(
            Text(content=field.before_cursor, style=text_wrap_none),
            Text(content=at_cursor, style=text_wrap_none | CURSOR, handle=field.cursor_cell),
            Text(content=field.after_cursor, style=text_wrap_none),
            Text(content=ghost, style=text_wrap_none | text_color("slate", 500)),
        ),
    )


def option_rows[T](
    shown: Sequence[T],
    highlighted: int | None,
    row_handle: ElementHandle,
    choose: Callable[[T], InputResponse],
    label: Callable[[T], str] = str,
) -> Div:
    """A row per option, the highlighted one marked and given `row_handle`, each choosing its option on a click."""
    return Div(
        style=col | max_height(4) | overflow_y_scroll,
        children=tuple(
            Text(
                content=label(option),
                style=text_wrap_none | (text_bg("sky", 800) if index == highlighted else Style()),
                handle=row_handle if index == highlighted else None,
                on_input=on_click(partial(choose, option)),
            )
            for index, option in enumerate(shown)
        ),
    )


# --8<-- [end:shared]

# --8<-- [start:combobox]


@dataclass(frozen=True, slots=True)
class Suggesting:
    highlight: Highlight = Highlight()
    is_open: bool = True


@component
def package_field(text: str, set_text: Setter[str]) -> Div:
    suggesting, set_suggesting = use_state(Suggesting(is_open=False))
    row_handle, _ = use_state(ElementHandle)

    def edit(edit_text: Callable[[str], str]) -> str:
        before = get_state(set_text)
        if (after := set_text(edit_text)) != before:
            set_suggesting(Suggesting())
        return after

    field = use_text_input(text, edit, auto_focus=True)
    shown = subsequence_matches(text, PACKAGES)
    is_open = field.focus.is_focused and suggesting.is_open and bool(shown)

    def choose(package: str) -> InputResponse:
        set_text(package)
        set_suggesting(Suggesting(is_open=False))
        return ()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_suggesting)
        now_shown = subsequence_matches(get_state(set_text), PACKAGES)
        is_showing = now.is_open and bool(now_shown)
        index = now.highlight.index_in(now_shown)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key) if now_shown:
                by = 1 if key == Key.Down else -1
                if is_showing:
                    highlight = now.highlight.moved(now_shown, by, ends="stop")
                else:
                    highlight = Highlight(index=0 if by == 1 else len(now_shown) - 1)
                set_suggesting(Suggesting(highlight=highlight))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ | Key.Tab) if is_showing and index is not None:
                return choose(now_shown[index])
            case KeyPressed(key=Key.Escape) if is_showing:
                set_suggesting(replace(now, is_open=False))
                return ()
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(24),
        on_input=on_input,
        children=(
            field_row(field),
            *((option_rows(shown, suggesting.highlight.index_in(shown), row_handle, choose),) if is_open else ()),
        ),
    )


# --8<-- [end:combobox]


@component
def add_package() -> Div:
    package, set_package = use_state("")
    return Div(
        style=col | pad_x(1),
        children=(
            Text(content="Add a package", style=text_color("slate", 400)),
            package_field(package, set_package),
        ),
    )


# --8<-- [start:palette]


@component
def command_palette(run: Callable[[str], InputResponse]) -> Div:
    query, set_query = use_state(Query())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(query.text, lambda edit: set_query(lambda q: q.edited(edit(q.text))).text, auto_focus=True)
    shown = substring_matches(query.text, COMMANDS)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_query)
        now_shown = substring_matches(now.text, COMMANDS)
        index = now.highlight.index_in(now_shown)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                set_query(replace(now, highlight=now.highlight.moved(now_shown, 1 if key == Key.Down else -1)))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ) if index is not None:
                return run(now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(24) | border | border_lightrounded,
        on_input=on_input,
        children=(
            field_row(field),
            option_rows(shown, query.highlight.index_in(shown), row_handle, run),
        ),
    )


# --8<-- [end:palette]


@component
def palette() -> Div:
    ran, set_ran = use_state("nothing yet")

    def run(command: str) -> InputResponse:
        set_ran(command)
        return ()

    return Div(style=col | pad_x(1), children=(command_palette(run), Text(content=f"Ran: {ran}")))


# --8<-- [start:search]


@dataclass(frozen=True, slots=True)
class Search:
    text: str = ""
    highlight: Highlight | None = None

    def edited(self, text: str) -> Search:
        return self if text == self.text else Search(text=text)


@component
def search_box(search: Callable[[str], InputResponse]) -> Div:
    query, set_query = use_state(Search())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(query.text, lambda edit: set_query(lambda s: s.edited(edit(s.text))).text, auto_focus=True)
    shown = substring_matches(query.text, QUERIES) if query.text else ()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_query)
        now_shown = substring_matches(now.text, QUERIES) if now.text else ()
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key) if now_shown:
                by = 1 if key == Key.Down else -1
                highlight = (
                    Highlight(index=0 if by == 1 else len(now_shown) - 1)
                    if now.highlight is None
                    else now.highlight.moved(now_shown, by, ends="release")
                )
                set_query(replace(now, highlight=highlight))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ):
                index = None if now.highlight is None else now.highlight.index_in(now_shown)
                return search(now.text if index is None else now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    highlighted = None if query.highlight is None else query.highlight.index_in(shown)
    return Div(
        style=col | width(24),
        on_input=on_input,
        children=(field_row(field), option_rows(shown, highlighted, row_handle, search)),
    )


# --8<-- [end:search]


@component
def searches() -> Div:
    searched, set_searched = use_state("nothing yet")

    def search(text: str) -> InputResponse:
        set_searched(text)
        return ()

    return Div(style=col | pad_x(1), children=(Text(content=f"Searched: {searched}"), search_box(search)))


# --8<-- [start:cycling]


@dataclass(frozen=True, slots=True)
class Cycling:
    stem: str
    highlight: Highlight


@dataclass(frozen=True, slots=True)
class Line:
    text: str = ""
    cycling: Cycling | None = None

    def edited(self, text: str) -> Line:
        return self if text == self.text else Line(text=text)


@component
def command_line() -> Div:
    line, set_line = use_state(Line())
    field = use_text_input(
        line.text, lambda edit: set_line(lambda now: now.edited(edit(now.text))).text, auto_focus=True
    )

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Tab | Key.BackTab as key):
                now = get_state(set_line)
                by = 1 if key == Key.Tab else -1
                stem = now.text if now.cycling is None else now.cycling.stem
                if not (matches := prefix_matches(stem, PROGRAMS)):
                    return ()
                if now.cycling is None:
                    highlight = Highlight(index=0 if by == 1 else len(matches) - 1).landed(matches)
                else:
                    highlight = now.cycling.highlight.moved(matches, by)
                set_line(Line(text=matches[highlight.index], cycling=Cycling(stem=stem, highlight=highlight)))
                return ()
            case _:
                return field.on_input(event, receiver)

    return Div(style=row | pad_x(1), on_input=on_input, children=(Text(content="$ "), field_row(field)))


# --8<-- [end:cycling]

# --8<-- [start:inline]


def suggestion(typed: str) -> str | None:
    """The first line of history that starts with `typed` and goes on past it, if `typed` isn't empty."""
    return next((line for line in HISTORY if line.startswith(typed) and line != typed), None) if typed else None


@component
def shell_prompt() -> Div:
    text, set_text = use_state("")
    field = use_text_input(text, set_text, auto_focus=True)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Right) if (
                field.latest_cursor() == len(now := get_state(set_text)) and (line := suggestion(now)) is not None
            ):
                set_text(line)
                return ()
            case _:
                return field.on_input(event, receiver)

    ghost = line[len(text) :] if (line := suggestion(text)) is not None else ""
    return Div(style=row | pad_x(1), on_input=on_input, children=(Text(content="$ "), field_row(field, ghost=ghost)))


# --8<-- [end:inline]

# --8<-- [start:refreshing]


@dataclass(frozen=True, slots=True)
class Process:
    pid: int
    command: str


def pid_of(process: Process) -> int:
    return process.pid


@component
def process_list(processes: tuple[Process, ...], stop: Callable[[Process], InputResponse]) -> Div:
    query, set_query = use_state(Query())
    row_handle, _ = use_state(ElementHandle)

    def matching(typed: str) -> tuple[Process, ...]:
        return substring_matches(typed, processes, key=lambda process: f"{process.pid} {process.command}")

    def edited(edit: Callable[[str], str]) -> Callable[[Query], Query]:
        def updated(query: Query) -> Query:
            if (text := edit(query.text)) == query.text:
                return query
            return Query(text=text, highlight=Highlight().landed(matching(text), pid_of))

        return updated

    field = use_text_input(query.text, lambda edit: set_query(edited(edit)).text, auto_focus=True)
    shown = matching(query.text)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_query)
        now_shown = matching(now.text)
        index = now.highlight.index_in(now_shown, pid_of)
        match event:
            case KeyPressed(key=Key.Down | Key.Tab | Key.ControlN):
                set_query(replace(now, highlight=now.highlight.moved(now_shown, 1, pid_of)))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Up | Key.BackTab | Key.ControlP | Key.ControlK):
                set_query(replace(now, highlight=now.highlight.moved(now_shown, -1, pid_of)))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.ControlX) if index is not None:
                return stop(now_shown[index])
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(30),
        on_input=on_input,
        children=(
            field_row(field),
            option_rows(
                shown,
                query.highlight.index_in(shown, pid_of),
                row_handle,
                stop,
                label=lambda process: f"{process.pid:>5} {process.command}",
            ),
        ),
    )


# --8<-- [end:refreshing]

# Each process starts listening this many seconds in, the newest at the top, as a listing sorted by start time is.
STARTS = (
    (6, Process(pid=4410, command="vite")),
    (3, Process(pid=3301, command="uvicorn")),
    (0, Process(pid=2048, command="postgres")),
    (0, Process(pid=1203, command="nginx")),
)


@component
def processes() -> Div:
    tick = use_clock(timedelta(seconds=1))
    stopped, set_stopped = use_state(frozenset[int]())
    seconds = tick.since_mount.total_seconds()
    listening = tuple(process for start, process in STARTS if start <= seconds and process.pid not in stopped)

    def stop(process: Process) -> InputResponse:
        set_stopped(lambda stopped: stopped | {process.pid})
        return ()

    return Div(
        style=col | pad_x(1),
        children=(
            Text(content="Ctrl+X stops a process", style=text_color("slate", 400)),
            process_list(listening, stop),
        ),
    )


# --8<-- [start:marks]


@dataclass(frozen=True, slots=True)
class Worktree:
    branch: str
    is_dirty: bool = False


WORKTREES = (
    Worktree(branch="feature/pickers"),
    Worktree(branch="fix/cursor", is_dirty=True),
    Worktree(branch="fix/resize"),
    Worktree(branch="docs/inline"),
)


def branch_of(worktree: Worktree) -> str:
    return worktree.branch


@component
def cleanup(remove: Callable[[frozenset[str]], InputResponse]) -> Div:
    query, set_query = use_state(Query())
    marked, set_marked = use_state(frozenset[str]())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(query.text, lambda edit: set_query(lambda q: q.edited(edit(q.text))).text, auto_focus=True)
    shown = subsequence_matches(query.text, WORKTREES, key=branch_of)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_query)
        now_shown = subsequence_matches(now.text, WORKTREES, key=branch_of)
        index = now.highlight.index_in(now_shown, branch_of)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                set_query(
                    replace(now, highlight=now.highlight.moved(now_shown, 1 if key == Key.Down else -1, branch_of))
                )
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=" ") if index is not None:
                if not (worktree := now_shown[index]).is_dirty:
                    set_marked(lambda marked: marked ^ {worktree.branch})
                return ()
            case KeyPressed(key=Key.Enter | Key.ControlJ):
                return remove(marks) if (marks := get_state(set_marked)) else ()
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    def label(worktree: Worktree) -> str:
        return (
            f"{'x' if worktree.branch in marked else ' '} {worktree.branch}{' (changes)' if worktree.is_dirty else ''}"
        )

    return Div(
        style=col | width(30),
        on_input=on_input,
        children=(
            Text(content=f"{len(marked)} marked"),
            field_row(field),
            option_rows(shown, query.highlight.index_in(shown, branch_of), row_handle, lambda _: (), label=label),
        ),
    )


# --8<-- [end:marks]


@component
def worktrees() -> Div:
    removed, set_removed = use_state(frozenset[str]())

    def remove(branches: frozenset[str]) -> InputResponse:
        set_removed(branches)
        return ()

    return Div(
        style=col | pad_x(1),
        children=(
            cleanup(remove),
            Text(content=f"Removed: {', '.join(sorted(removed)) or 'nothing yet'}", style=text_color("slate", 400)),
        ),
    )


# --8<-- [start:headings]


@dataclass(frozen=True, slots=True)
class Row:
    name: str
    is_heading: bool = False


def is_heading(row: Row) -> bool:
    return row.is_heading


SECTIONS = {"CPython": ("3.13", "3.14", "3.15", "3.15t"), "PyPy": ("pypy3.10", "pypy3.11")}


def rows_for(text: str) -> tuple[Row, ...]:
    """The versions that contain `text`, each section's under its heading, leaving out sections with none."""
    return tuple(
        row
        for heading, versions in SECTIONS.items()
        if (matched := substring_matches(text, versions))
        for row in (Row(name=heading, is_heading=True), *(Row(name=version) for version in matched))
    )


@component
def python_picker(choose: Callable[[str], InputResponse]) -> Div:
    query, set_query = use_state(Query())
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(query.text, lambda edit: set_query(lambda q: q.edited(edit(q.text))).text, auto_focus=True)
    shown = rows_for(query.text)
    highlighted = query.highlight.index_in(shown, is_disabled=is_heading)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        now = get_state(set_query)
        now_shown = rows_for(now.text)
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                by = 1 if key == Key.Down else -1
                set_query(replace(now, highlight=now.highlight.moved(now_shown, by, is_disabled=is_heading)))
                return ScrollIntoView(row_handle, block="nearest")
            case KeyPressed(key=Key.Enter | Key.ControlJ) if (
                index := now.highlight.index_in(now_shown, is_disabled=is_heading)
            ) is not None:
                return choose(now_shown[index].name)
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    return Div(
        style=col | width(20),
        on_input=on_input,
        children=(
            field_row(field),
            *(
                Text(
                    content=row.name if row.is_heading else f"  {row.name}",
                    style=text_wrap_none
                    | (text_bold | text_color("amber", 300) if row.is_heading else Style())
                    | (text_bg("sky", 800) if index == highlighted else Style()),
                    handle=row_handle if index == highlighted else None,
                )
                for index, row in enumerate(shown)
            ),
        ),
    )


# --8<-- [end:headings]


@component
def pythons() -> Div:
    chosen, set_chosen = use_state("3.15")

    def choose(version: str) -> InputResponse:
        set_chosen(version)
        return ()

    return Div(style=col | pad_x(1), children=(Text(content=f"Python {chosen}"), python_picker(choose)))


# --8<-- [start:preview]

COLORS: tuple[ColorName, ...] = ("red", "orange", "amber", "lime", "green", "teal", "sky", "indigo", "violet", "pink")


@component
def color_list(query: Query, set_query: Setter[Query]) -> Div:
    row_handle, _ = use_state(ElementHandle)
    field = use_text_input(query.text, lambda edit: set_query(lambda q: q.edited(edit(q.text))).text, auto_focus=True)
    shown = substring_matches(query.text, COLORS)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                by = 1 if key == Key.Down else -1
                set_query(lambda q: replace(q, highlight=q.highlight.moved(substring_matches(q.text, COLORS), by)))
                return ScrollIntoView(row_handle, block="nearest")
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, ScrollIntoView(row_handle, block="nearest"))

    def highlight(color: ColorName) -> InputResponse:
        set_query(lambda q: replace(q, highlight=Highlight(key=color)))
        return ()

    return Div(
        style=col | width(14),
        on_input=on_input,
        children=(field_row(field), option_rows(shown, query.highlight.index_in(shown), row_handle, highlight)),
    )


@component
def swatches() -> Div:
    query, set_query = use_state(Query())
    shown = substring_matches(query.text, COLORS)
    index = query.highlight.index_in(shown)
    return Div(
        style=row | gap(2) | pad_x(1),
        children=(
            color_list(query, set_query),
            Div(
                style=size(12, 5)
                | (content_color(shown[index], 500) if index is not None else border | border_lightrounded),
                children=(Text(content="nothing" if index is None else shown[index], style=pad_x(1)),),
            ),
        ),
    )


# --8<-- [end:preview]

# --8<-- [start:widget]


@component
def dependency_form() -> Div:
    package, set_package = use_state("")
    group, set_group = use_state("")
    return Div(
        style=col | pad_x(1),
        on_input=tab_focus,
        children=(
            combobox(package, set_package, PACKAGES, placeholder="Package", style=width(24), auto_focus=True),
            text_input(group, set_group, placeholder="Group", style=width(24)),
        ),
    )


# --8<-- [end:widget]


ROOTS = (
    add_package,
    palette,
    searches,
    command_line,
    shell_prompt,
    processes,
    worktrees,
    pythons,
    swatches,
    dependency_form,
)

# --8<-- [start:scenes]

from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import paced
from counterweight.autopilot import typed
from counterweight.components import Component
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

DOWN = KeyPressed(key=Key.Down)
UP = KeyPressed(key=Key.Up)
ENTER = KeyPressed(key=Key.Enter)
ESCAPE = KeyPressed(key=Key.Escape)
TAB = KeyPressed(key=Key.Tab)
BACK_TAB = KeyPressed(key=Key.BackTab)
RIGHT = KeyPressed(key=Key.Right)
LEFT = KeyPressed(key=Key.Left)
SPACE = KeyPressed(key=" ")
PAUSE = AdvanceClock(by=timedelta(milliseconds=500))
LINGER = AdvanceClock(by=timedelta(seconds=2))

FOUR_SECONDS = AdvanceClock(by=timedelta(seconds=4))

STILLS = [
    Still("options-combobox", add_package(), (30, 7), steps=[*typed("py"), DOWN]),
    Still("options-palette", palette(), (30, 10), steps=[*typed("f"), DOWN]),
    Still("options-search", searches(), (30, 6), steps=[*typed("python"), DOWN]),
    Still("options-cycling", command_line(), (30, 1), steps=[*typed("c"), TAB, TAB]),
    Still("options-inline", shell_prompt(), (40, 1), steps=typed("git s")),
    Still("options-refreshing", processes(), (32, 7), steps=[DOWN, FOUR_SECONDS]),
    Still("options-marks", worktrees(), (32, 7), steps=[SPACE, DOWN, DOWN, SPACE]),
    Still("options-headings", pythons(), (22, 10), steps=[DOWN, DOWN, DOWN, DOWN]),
    Still("options-preview", swatches(), (30, 6), steps=[DOWN, DOWN]),
    Still("options-widget", dependency_form(), (30, 10), steps=[*typed("py"), DOWN]),
]


def demo(name: str, root: Component, dimensions: tuple[int, int], steps: list[AutopilotStep]) -> Demo:
    """A demo of `steps` at a person's pace, lingering on the last frame."""
    return Demo(name, root, dimensions, steps=[*paced(steps, pause=PAUSE), LINGER])


DEMOS = [
    demo("options-combobox", add_package(), (30, 7), [*typed("py"), DOWN, ENTER, ESCAPE, UP, UP, ENTER]),
    demo("options-palette", palette(), (30, 10), [*typed("f"), DOWN, ENTER, UP, UP, ENTER]),
    demo("options-search", searches(), (30, 6), [*typed("python"), DOWN, DOWN, ENTER, DOWN, DOWN, DOWN, ENTER]),
    demo("options-cycling", command_line(), (30, 1), [*typed("c"), TAB, TAB, TAB, BACK_TAB, *typed("h")]),
    demo("options-inline", shell_prompt(), (40, 1), [*typed("git s"), RIGHT, *typed("j"), LEFT, LEFT, RIGHT]),
    demo("options-refreshing", processes(), (32, 7), [DOWN, FOUR_SECONDS, DOWN, KeyPressed(key=Key.ControlX)]),
    demo("options-marks", worktrees(), (32, 7), [SPACE, DOWN, SPACE, DOWN, SPACE, ENTER]),
    demo("options-headings", pythons(), (22, 10), [DOWN, DOWN, DOWN, DOWN, ENTER, *typed("py"), ENTER]),
    demo("options-preview", swatches(), (30, 6), [DOWN, DOWN, *typed("i"), DOWN]),
    demo("options-widget", dependency_form(), (30, 10), [*typed("py"), DOWN, TAB, TAB, BACK_TAB]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
