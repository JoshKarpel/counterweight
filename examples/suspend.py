import os
import subprocess
import sys
from asyncio import run
from functools import partial
from pathlib import Path

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Suspend
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | justify_children_center,
        children=[
            Text(content="Suspend Demo", style=text_amber_600 | weight_none),
            picker(),
        ],
    )


def clamp(min_: int, val: int, max_: int) -> int:
    return max(min_, min(val, max_))


def open_editor(file: Path) -> None:
    subprocess.run(
        [os.environ.get("EDITOR", "vim"), str(file)],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


@component
def picker() -> Div:
    glob, set_glob = use_state("**/*.py")
    selected_file_idx, set_selected_file_idx = use_state(0)

    files = sorted(Path.cwd().rglob(glob))

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Enter:
                return Suspend(handler=partial(open_editor, files[selected_file_idx]))
            case Key.Down:
                set_selected_file_idx(lambda i: clamp(0, i + 1, len(files) - 1))
            case Key.Up:
                set_selected_file_idx(lambda i: clamp(0, i - 1, len(files) - 1))
            case Key.Backspace:
                new_glob = glob[:-1]
                set_selected_file_idx(0)
                set_glob(new_glob)
            case c if c.isprintable() and len(c) == 1:
                new_glob = glob + c
                set_selected_file_idx(0)
                set_glob(new_glob)

        return None

    return Div(
        style=col | align_self_stretch | justify_children_center | border_lightrounded,
        on_key=on_key,
        children=[
            glob_input(glob=glob),
            file_list(files=files, selected_idx=selected_file_idx),
        ],
    )


@component
def glob_input(glob: str) -> Div:
    return Div(
        style=row | align_self_stretch | border_bottom | weight_none,
        children=[
            Text(style=weight_none | border_right | pad_x_1, content="glob"),
            Text(style=weight_none | pad_x_1, content=glob),
        ],
    )


@component
def file_list(files: list[Path], selected_idx: int) -> Div:
    start_idx = max(0, selected_idx - 5)
    return Div(
        style=col | justify_children_start | pad_x_1,
        children=[
            Text(
                style=weight_none | (text_cyan_700 if idx == selected_idx else None),
                content=str(file.relative_to(Path.cwd())),
            )
            for idx, file in enumerate(files[start_idx : start_idx + 10], start=start_idx)
        ],
    )


if __name__ == "__main__":
    run(app(root))
