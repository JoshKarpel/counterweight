import os
import subprocess
import sys
from asyncio import run, to_thread
from collections.abc import Callable
from functools import partial
from pathlib import Path

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ScrollIntoView, Suspend
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import use_text_input
from counterweight.hooks import ElementHandle, use_effect, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from counterweight.utils import clamp

CURSOR = text_color("slate", 900) | text_bg("slate", 100)


@component
def root() -> Div:
    return Div(
        style=col | full | justify_children_start | pad(1),
        children=(
            Text(content="Suspend Demo", style=text_color("amber", 600) | text_justify_center | pad_bottom(1)),
            Div(
                style=row | gap(1) | pad_bottom(1),
                children=(
                    Text(content="↑ / ↓  navigate", style=text_color("slate", 400)),
                    Text(content="|", style=text_color("slate", 600)),
                    Text(content="type  edit glob", style=text_color("slate", 400)),
                    Text(content="|", style=text_color("slate", 600)),
                    Text(content="⏎  open in $EDITOR", style=text_color("slate", 400)),
                ),
            ),
            picker(),
        ),
    )


def _list_files(glob: str) -> tuple[Path, ...]:
    cwd = Path.cwd()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", glob],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return tuple(sorted(cwd.rglob(glob)))
    return tuple(sorted(cwd / f for f in result.stdout.splitlines() if f))


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
    files, set_files = use_state(tuple[Path, ...]())
    selected_file_idx, set_selected_file_idx = use_state(0)
    # On the selected row, so moving the selection can scroll it into view.
    selected_row, _ = use_state(ElementHandle)

    # In a thread, so typing in the glob field doesn't wait on git, and only when the glob changes.
    async def list_files() -> None:
        set_files(await to_thread(_list_files, glob))

    use_effect(list_files, deps=(glob,))

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter) if files:
                return Suspend(handler=partial(open_editor, files[selected_file_idx]))
            case KeyPressed(key=Key.Down):
                set_selected_file_idx(lambda i: clamp(0, i + 1, len(files) - 1))
                return ScrollIntoView(selected_row, block="center")
            case KeyPressed(key=Key.Up):
                set_selected_file_idx(lambda i: clamp(0, i - 1, len(files) - 1))
                return ScrollIntoView(selected_row, block="center")
            case _:
                return None

    def edit_glob(edit: Callable[[str], str]) -> None:
        def apply(glob: str) -> str:
            if (edited := edit(glob)) != glob:
                set_selected_file_idx(0)
            return edited

        set_glob(apply)

    return Div(
        style=col | fill(1) | justify_children_start | border_collapse,
        on_input=on_input,
        children=(
            glob_input(glob=glob, set_glob=edit_glob),
            # Keyed by the glob, so editing it remounts the list, which starts it scrolled to its top.
            file_list(files=files, selected_idx=selected_file_idx, selected_row=selected_row).with_key(glob),
        ),
    )


@component
def glob_input(glob: str, set_glob: Callable[[Callable[[str], str]], None]) -> Div:
    field = use_text_input(glob, set_glob, auto_focus=True)
    return Div(
        style=row | align_self_stretch | border_collapse,
        on_input=field.on_input,
        children=(
            Text(style=content_box | border | pad_x(1), content="glob"),
            Div(
                style=content_box | border | pad_x(1) | fill(1),
                children=(
                    Div(
                        style=row | overflow_x_scroll | stick_to_end_x,
                        on_input=field.on_press,
                        children=(
                            Text(content=field.before_cursor, style=text_wrap_none),
                            Text(content=field.at_cursor, style=text_wrap_none | CURSOR, handle=field.cursor_cell),
                            Text(content=field.after_cursor, style=text_wrap_none),
                        ),
                    ),
                ),
            ),
        ),
    )


@component
def file_list(files: tuple[Path, ...], selected_idx: int, selected_row: ElementHandle) -> Div:
    return Div(
        style=col | justify_children_start | pad_x(1) | border | border_lightrounded | fill(1) | overflow_y_scroll,
        on_input=scroll_on_wheel(),
        children=tuple(
            Text(
                style=text_color("cyan", 300) if idx == selected_idx else default,
                content=str(file.relative_to(Path.cwd())),
                handle=selected_row if idx == selected_idx else None,
            )
            for idx, file in enumerate(files)
        ),
    )


if __name__ == "__main__":
    run(app(root()))
