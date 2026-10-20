from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples import gallery
from counterweight.examples.catalog import examples
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.geometry import Position
from counterweight.keys import Key

ENTRIES = gallery.entries(examples())

OTHER = "box-model"


async def screen(root: Component, steps: Sequence[AutopilotStep], dimensions: tuple[int, int] = (120, 40)) -> str:
    return (await frame_of(Still("test", root, dimensions, steps))).text(ansi=False)


def gallery_of(entry: gallery.Entry) -> tuple[Component, list[KeyPressed]]:
    """A gallery of `entry`'s example and one other, and the keys that select `entry` in it."""
    only = (entry.example.name, "todo" if entry.example.name == OTHER else OTHER)
    names = [line.name for line in gallery.entries([example for example in examples() if example.name in only])]
    return gallery.root(only=only), [KeyPressed(key=Key.Down)] * names.index(entry.name)


@pytest.mark.parametrize("tabs", [0, 1, 2], ids=lambda tabs: f"{tabs} tabs")
@pytest.mark.parametrize("entry", ENTRIES, ids=lambda entry: entry.name)
async def test_ctrl_right_bracket_brings_focus_back_to_the_list_from_any_example(
    entry: gallery.Entry, tabs: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    root, select = gallery_of(entry)
    running = [*select, KeyPressed(key=Key.Enter), *[KeyPressed(key=Key.Tab)] * tabs]

    # Home and End move the selection off the example only if the list has focus, which stops the example.
    shown = await screen(
        root, [*running, KeyPressed(key=Key.ControlRightBracket), *[KeyPressed(key=key) for key in (Key.Home, Key.End)]]
    )

    assert "Press Enter to run it." in shown


@pytest.mark.parametrize(
    "entry",
    # A root that makes itself focusable, and one that doesn't.
    [entry for entry in ENTRIES if entry.name in ("text-input:command-line", "box-model")],
    ids=lambda entry: entry.name,
)
async def test_enter_moves_focus_back_into_an_example_that_is_still_running(entry: gallery.Entry) -> None:
    root, select = gallery_of(entry)
    back_and_in = [*select, *(KeyPressed(key=key) for key in (Key.Enter, Key.ControlRightBracket, Key.Enter))]

    # Down moves the selection off the example, which stops it, only if the list has focus.
    shown = await screen(root, [*back_and_in, KeyPressed(key=Key.Down)])

    assert "Press Enter to run it." not in shown


SOME = gallery.root(only=("todo", "box-model", "layout-splitting"))


def selected(shown: str) -> str:
    """The name on the list's selected line."""
    return next(line.split("▸ ")[1].split()[0] for line in shown.splitlines() if "▸ " in line)


@pytest.mark.parametrize(
    ("moves", "expected"),
    [
        ([Key.PageDown], "layout-splitting:nested-grid"),
        ([Key.PageDown, Key.PageDown], "layout-splitting:percent-gap"),
        ([Key.End, Key.PageUp], "layout-splitting:equal-flex"),
        ([Key.Down, Key.Down, Key.Up], "box-model"),
        ([Key.Up], "todo"),
    ],
)
async def test_the_list_moves_its_selection_with_the_keys_and_stops_at_its_ends(
    moves: list[str], expected: str
) -> None:
    assert selected(await screen(SOME, [KeyPressed(key=key) for key in moves])) == expected


async def test_a_move_that_leaves_the_selection_where_it_is_leaves_the_example_running() -> None:
    running = [KeyPressed(key=key) for key in (Key.Enter, Key.ControlRightBracket)]

    shown = await screen(SOME, [*running, KeyPressed(key=Key.Up), KeyPressed(key=Key.Home)])

    assert "Press Enter to run it." not in shown


async def test_a_click_on_an_example_selects_it_and_focuses_the_list() -> None:
    before = await screen(SOME, [])
    row = next(row for row, line in enumerate(before.splitlines()) if "box-model" in line)
    click: list[AutopilotStep] = [
        MouseDown(absolute=Position(5, row), button=1),
        MouseUp(absolute=Position(5, row), button=1),
    ]

    shown = await screen(SOME, [KeyPressed(key=Key.Enter), *click, KeyPressed(key=Key.Down)])

    assert selected(shown) == "layout-splitting:equal-flex"


async def test_s_hides_the_source_and_shows_it_again() -> None:
    hidden = await screen(SOME, [KeyPressed(key="s")])
    shown = await screen(SOME, [KeyPressed(key="s"), KeyPressed(key="s")])

    assert ("Source" in hidden, "Source" in shown) == (False, True)


async def test_c_copies_the_example_into_the_working_directory_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    # The notice doesn't wrap, and macOS's temporary directories are too deep for it to fit the default width.
    dimensions = (len(f"{tmp_path / 'todo.py'} already exists, so it's left as it is"), 40)
    copied = await screen(SOME, [KeyPressed(key="c")], dimensions)
    again = await screen(SOME, [KeyPressed(key="c")], dimensions)

    assert (f"Copied todo to {tmp_path / 'todo.py'}" in copied, "already exists" in again) == (True, True)


async def test_c_says_why_it_could_not_copy_the_example(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    read_only = tmp_path / "read-only"
    read_only.mkdir(mode=0o500)
    monkeypatch.chdir(read_only)

    shown = await screen(SOME, [KeyPressed(key="c")])

    assert "Couldn't copy todo: Permission denied" in shown
