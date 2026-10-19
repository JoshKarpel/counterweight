"""
A Markdown viewer: a tree of a directory's Markdown files on the left, and the chosen file rendered on the right.

Run it with `uv run python -m examples.markdown_viewer [directory]`; it shows the docs by default.
Each pane is a scroll area: Tab moves focus between them, as does a click,
and the focused pane's border lights up.
In the tree, Up and Down move through it, Home and End to its first and last lines,
Right or Enter opens a directory or shows a file, Left closes a directory,
and clicking a row does what Enter would.
In the document, the arrows, PageUp, PageDown, Home and End scroll it,
and the wheel scrolls whichever pane is under the pointer.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from counterweight.app import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import FocusOn
from counterweight.controls import ScrollIntoView
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.headless import use_scroll_area
from counterweight.hooks import ElementHandle
from counterweight.hooks import FocusHandle
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown_document
from counterweight.styles import Style
from counterweight.styles.utilities import *


@dataclass(frozen=True, slots=True)
class File:
    path: Path
    source: str


@dataclass(frozen=True, slots=True)
class Directory:
    path: Path
    entries: tuple[Directory | File, ...]


type Entry = Directory | File


@dataclass(frozen=True, slots=True)
class Line:
    """One visible line of the tree: an entry, indented by its depth."""

    entry: Entry
    depth: int


def scan(path: Path) -> Directory:
    """`path`'s Markdown files and the directories that hold any, read once, before the app starts."""
    directories = [scan(child) for child in sorted(path.iterdir()) if child.is_dir()]
    files = [File(path=child, source=child.read_text()) for child in sorted(path.iterdir()) if child.suffix == ".md"]
    return Directory(path=path, entries=(*[d for d in directories if d.entries], *files))


def visible_lines(directory: Directory, expanded: frozenset[Path], depth: int = 0) -> Iterator[Line]:
    for entry in directory.entries:
        yield Line(entry=entry, depth=depth)
        if isinstance(entry, Directory) and entry.path in expanded:
            yield from visible_lines(entry, expanded, depth + 1)


def first_file(directory: Directory) -> File | None:
    """The directory's index or README if it has one, or else its first file."""
    files = [entry for entry in directory.entries if isinstance(entry, File)]
    return next((file for file in files if file.path.stem.lower() in {"index", "readme"}), next(iter(files), None))


@component
def root(tree: Directory) -> Div:
    expanded, set_expanded = use_state(frozenset[Path]())
    cursor, set_cursor = use_state(0)
    shown, set_shown = use_state(first_file(tree))
    # On the cursor's line, so moving the cursor can scroll it into view.
    cursor_line, _ = use_state(ElementHandle)
    tree_focus, _ = use_state(FocusHandle)

    lines = list(visible_lines(tree, expanded))

    def activate(index: int) -> FocusOn:
        """Does what Enter on the line at `index` does, and focuses the tree, as a click on a list's item would."""
        set_cursor(index)
        match lines[index].entry:
            case Directory(path=path):
                set_expanded(expanded ^ {path})
            case File() as file:
                set_shown(file)
        return FocusOn(tree_focus)

    def move_cursor(index: int) -> InputResponse:
        set_cursor(index)
        return ScrollIntoView(cursor_line, block="nearest")

    def on_tree_key(event: InputEvent, _: Receiver) -> InputResponse:
        if not lines:
            return None
        match event:
            case KeyPressed(key=Key.Up):
                return move_cursor(max(cursor - 1, 0))
            case KeyPressed(key=Key.Down):
                return move_cursor(min(cursor + 1, len(lines) - 1))
            case KeyPressed(key=Key.Home):
                return move_cursor(0)
            case KeyPressed(key=Key.End):
                return move_cursor(len(lines) - 1)
            case KeyPressed(key=Key.Right | Key.Enter):
                match lines[cursor].entry:
                    case Directory(path=path):
                        set_expanded(expanded | {path})
                    case File() as file:
                        set_shown(file)
            case KeyPressed(key=Key.Left):
                match lines[cursor].entry:
                    case Directory(path=path) if path in expanded:
                        set_expanded(expanded - {path})
                    case _:
                        return move_cursor(parent_line(lines, cursor))
            case _:
                return None
        return ()

    return Div(
        style=row | full,
        on_input=tab_focus,
        children=(
            pane(
                f"{tree.path.name}/",
                length(32),
                tuple(
                    tree_line(
                        line,
                        handle=cursor_line if index == cursor else None,
                        is_shown=line.entry == shown,
                        expanded=expanded,
                        on_press=on_click(partial(activate, index)),
                    )
                    for index, line in enumerate(lines)
                ),
                # First, so the tree's keys move its cursor rather than scroll it.
                on_key=on_tree_key,
                handle=tree_focus,
                auto_focus=True,
            ),
            pane(
                str(shown.path.relative_to(tree.path)) if shown else "",
                fill(1),
                (markdown_document(shown.source) if shown else Text(content="No Markdown files here."),),
                # Keyed by the file, so showing another remounts the pane, which starts it scrolled to its top.
            ).with_key(str(shown.path) if shown else None),
        ),
    )


@component
def pane(
    name: str,
    width: Style,
    children: tuple[Component | AnyElement, ...],
    on_key: InputHandler | None = None,
    handle: FocusHandle | None = None,
    auto_focus: bool = False,
) -> Div:
    """
    A titled, bordered pane whose content scrolls with the keys while it's focused, and with the wheel.
    The border and title are on a box around the part that scrolls, so they stay put while it scrolls,
    and that box is the one that's focused, so its border can show it.
    """
    area = use_scroll_area(handle=handle, auto_focus=auto_focus)
    return Div(
        style=col
        | width
        | border
        | border_lightrounded
        | (border_color("sky", 400) if area.focus.is_focused else border_color("slate", 600)),
        on_input=first(on_key, area.on_input) if on_key else area.on_input,
        children=(
            Text(content=f" {name} " if name else "", style=title),
            Div(
                style=fill(1) | col | pad_x(1) | area.style,
                handle=area.viewport,
                children=children,
            ),
        ),
    )


title = position_absolute | inset_top(-1) | inset_left(1) | clip_to_border | text_color("slate", 400)


def parent_line(lines: list[Line], index: int) -> int:
    """The line of the directory holding the entry at `index`, or `index` itself at the top level."""
    depth = lines[index].depth
    return next((i for i in range(index - 1, -1, -1) if lines[i].depth < depth), index)


def tree_line(
    line: Line, handle: ElementHandle | None, is_shown: bool, expanded: frozenset[Path], on_press: InputHandler
) -> Text:
    match line.entry:
        case Directory(path=path):
            label = f"{'▾' if path in expanded else '▸'} {path.name}/"
            style = text_color("sky", 300)
        case File(path=path):
            label = f"  {path.name}"
            style = text_color("slate", 50) if is_shown else text_color("slate", 300)
    return Text(
        content=f"{'  ' * line.depth}{label}",
        style=style | (text_bg("slate", 700) if handle else None),
        handle=handle,
        on_input=on_press,
    )


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "docs"
    asyncio.run(app(root(scan(directory.resolve()))))
