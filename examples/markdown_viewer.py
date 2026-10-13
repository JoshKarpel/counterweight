"""
A Markdown viewer: a tree of a directory's Markdown files on the left, and the chosen file rendered on the right.

Run it with `uv run python -m examples.markdown_viewer [directory]`; it shows the docs by default.
Up and Down move through the tree, Right or Enter opens a directory or shows a file, Left closes a directory,
and clicking a row does what Enter would.
Documents longer than the screen are cut off at its bottom edge.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Receiver
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown
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

    lines = list(visible_lines(tree, expanded))

    def activate(index: int) -> None:
        set_cursor(index)
        match lines[index].entry:
            case Directory(path=path):
                set_expanded(expanded ^ {path})
            case File() as file:
                set_shown(file)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        if not lines:
            return None
        match event:
            case KeyPressed(key=Key.Up):
                set_cursor(max(cursor - 1, 0))
            case KeyPressed(key=Key.Down):
                set_cursor(min(cursor + 1, len(lines) - 1))
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
                        set_cursor(parent_line(lines, cursor))
            case _:
                return None
        return ()

    return Div(
        style=row,
        on_input=on_input,
        children=(
            Div(
                style=col
                | length(32)
                | border
                | border_bottom_0
                | border_lightrounded
                | border_color("slate", 600)
                | pad_x(1),
                children=(
                    Text(content=f" {tree.path.name}/ ", style=title),
                    *(
                        tree_line(
                            line,
                            is_cursor=index == cursor,
                            is_shown=line.entry == shown,
                            expanded=expanded,
                            on_press=on_click(partial(activate, index)),
                        )
                        for index, line in enumerate(lines)
                    ),
                ),
            ),
            Div(
                style=col
                | fill(1)
                | border
                | border_bottom_0
                | border_lightrounded
                | border_color("slate", 600)
                | pad_x(1),
                children=(
                    Text(content=f" {shown.path.relative_to(tree.path)} " if shown else "", style=title),
                    markdown(shown.source) if shown else Text(content="No Markdown files here."),
                ),
            ),
        ),
    )


title = position_absolute | inset_top(-1) | inset_left(1) | text_color("slate", 400)


def parent_line(lines: list[Line], index: int) -> int:
    """The line of the directory holding the entry at `index`, or `index` itself at the top level."""
    depth = lines[index].depth
    return next((i for i in range(index - 1, -1, -1) if lines[i].depth < depth), index)


def tree_line(line: Line, is_cursor: bool, is_shown: bool, expanded: frozenset[Path], on_press: InputHandler) -> Text:
    match line.entry:
        case Directory(path=path):
            label = f"{'▾' if path in expanded else '▸'} {path.name}/"
            style = text_color("sky", 300)
        case File(path=path):
            label = f"  {path.name}"
            style = text_color("slate", 50) if is_shown else text_color("slate", 300)
    return Text(
        content=f"{'  ' * line.depth}{label}",
        style=style | (text_bg("slate", 700) if is_cursor else None),
        on_input=on_press,
    )


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "docs"
    asyncio.run(app(root(scan(directory.resolve()))))
