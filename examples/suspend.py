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
from counterweight.hooks import use_rects, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from counterweight.utils import clamp


@component
def root() -> Div:
    return Div(
        style=col | full | align_children_stretch | justify_children_start | pad(1),
        children=[
            Text(content="Suspend Demo", style=text_color("amber", 600) | text_justify_center | pad_bottom(1)),
            Div(
                style=row | gap(1) | pad_bottom(1),
                children=[
                    Text(content="↑ / ↓  navigate", style=text_color("slate", 400)),
                    Text(content="|", style=text_color("slate", 600)),
                    Text(content="type  edit glob", style=text_color("slate", 400)),
                    Text(content="|", style=text_color("slate", 600)),
                    Text(content="⏎  open in $EDITOR", style=text_color("slate", 400)),
                ],
            ),
            picker(),
        ],
    )


def _list_files(glob: str) -> list[Path]:
    cwd = Path.cwd()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", glob],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return sorted(cwd.rglob(glob))
    return sorted(cwd / f for f in result.stdout.splitlines() if f)


def open_editor(file: Path) -> None:
    subprocess.run(
        [os.environ.get("EDITOR", "vim"), str(file)],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        check=False,
    )


@component
def picker() -> Div:
    glob, set_glob = use_state("**/*.py")
    selected_file_idx, set_selected_file_idx = use_state(0)

    files = _list_files(glob)

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
        style=col | grow(1) | justify_children_start | border_collapse,
        on_key=on_key,
        children=[
            glob_input(glob=glob),
            file_list(files=files, selected_idx=selected_file_idx),
        ],
    )


@component
def glob_input(glob: str) -> Div:
    return Div(
        style=row | align_self_stretch | border_collapse,
        children=[
            Text(style=content_box | border_light | pad_x(1), content="glob"),
            Text(style=content_box | border_light | pad_x(1) | grow(1), content=glob),
        ],
    )


@component
def file_list(files: list[Path], selected_idx: int) -> Div:
    rects = use_rects()
    visible = max(1, int(rects.content.height) + 1)
    start_idx = clamp(0, selected_idx - visible // 2, max(0, len(files) - visible))
    return Div(
        style=col | justify_children_start | pad_x(1) | border_lightrounded | grow(1),
        children=[
            Text(
                style=text_color("cyan", 300) if idx == selected_idx else default,
                content=str(file.relative_to(Path.cwd())),
            )
            for idx, file in enumerate(files[start_idx : start_idx + visible], start=start_idx)
        ],
    )


if __name__ == "__main__":
    run(app(root))
