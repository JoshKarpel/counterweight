"""
What the docs' snippets do beyond what their stills and demos show, such as the keys they ignore,
and the components their pages show without a scene of their own.
"""

from __future__ import annotations

import io
import os
from asyncio import wait_for
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

import pytest

from counterweight import app
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import WaitFor
from counterweight.autopilot import showing
from counterweight.autopilot import typed
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.examples.scenes import nothing_attached
from counterweight.examples.snippets import autocomplete
from counterweight.examples.snippets import autopilot_search
from counterweight.examples.snippets import commands
from counterweight.examples.snippets import draggable
from counterweight.examples.snippets import focus_form
from counterweight.examples.snippets import inline_picker
from counterweight.examples.snippets import input_controls
from counterweight.examples.snippets import input_handlers
from counterweight.examples.snippets import options
from counterweight.examples.snippets import performance_process_table
from counterweight.examples.snippets import picker
from counterweight.examples.snippets import prefix_keys
from counterweight.examples.snippets import programs
from counterweight.examples.snippets import pseudoterminals
from counterweight.examples.snippets import scrolling
from counterweight.examples.snippets import styles_merging
from counterweight.examples.snippets import terminals
from counterweight.examples.snippets import text_input
from counterweight.examples.snippets import use_controls_first_error
from counterweight.examples.snippets import use_effect_forecast
from counterweight.examples.snippets.terminals import PLAIN_SHELL
from counterweight.geometry import Position
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.paint import Frame
from counterweight.styles.utilities import text_bg
from tests.rendering import TIMEOUT
from tests.terminal import Terminal


async def screen(root: Component, steps: Sequence[AutopilotStep] = (), dimensions: tuple[int, int] = (60, 16)) -> str:
    """The text `root` shows after `steps`, rendered as a still is."""
    frame = await frame_of(Still("test", root, dimensions, steps))
    return "\n".join(line.rstrip() for line in frame.text(ansi=False).splitlines())


def keys(*names: str) -> list[KeyPressed]:
    return [KeyPressed(key=name) for name in names]


def press(x: int, y: int, button: int = 1) -> list[MouseDown | MouseUp]:
    return [MouseDown(absolute=Position(x, y), button=button), MouseUp(absolute=Position(x, y), button=button)]


async def test_the_fruit_search_scrolls_its_results_back_up() -> None:
    for search in (text_input.search, autopilot_search.search):
        shown = await screen(search(), keys(Key.Down, Key.Down, Key.Up))

        assert shown.splitlines()[2] == "banana"


async def test_a_prefix_followed_by_a_key_it_does_not_bind_does_nothing() -> None:
    assert await screen(prefix_keys.root(), keys(Key.ControlB, "z")) == await screen(prefix_keys.root())


async def test_a_log_with_no_failure_stays_at_its_start() -> None:
    shown = await screen(use_controls_first_error.results_log(("ok   tests/test_a.py", "ok   tests/test_b.py")))

    assert "ok   tests/test_a.py" in shown.splitlines()[1]


async def test_backspace_empties_the_basket() -> None:
    shown = await screen(input_handlers.basket(), keys(Key.Tab, Key.Enter, Key.Enter, Key.Backspace, Key.Enter))

    assert "Apples: 1 · Pears: 0" in shown


async def test_the_autocomplete_highlights_upward_and_closes_on_escape() -> None:
    typed = keys("p", "y")
    opened = await screen(autocomplete.root(), typed, (40, 14))
    upward = await screen(autocomplete.root(), (*typed, KeyPressed(key=Key.Up)), (40, 14))
    closed = await screen(autocomplete.root(), (*typed, KeyPressed(key=Key.Escape)), (40, 14))

    assert ("pydantic" in opened, upward != opened, "pydantic" in closed) == (True, True, False)


@pytest.mark.parametrize(
    ("steps", "printed"),
    [(keys(Key.Down, Key.Down, Key.Up, Key.Enter), "feature/inline-rendering\n"), (keys(Key.Escape), "")],
    ids=["upward", "escape"],
)
async def test_the_inline_picker_prints_the_branch_picked_or_nothing_on_escape(
    steps: list[KeyPressed], printed: str
) -> None:
    stdout = io.StringIO()

    await app(
        inline_picker.branch_picker(),
        headless=True,
        dimensions=(48, 8),
        viewport=inline_picker.VIEWPORT,
        stdout=stdout,
        autopilot=steps,
    )

    assert stdout.getvalue() == printed


async def test_the_picker_chooses_upward_and_closes_on_escape() -> None:
    opened = await screen(picker.settings(), keys(Key.F2), (40, 10))
    upward = await screen(picker.settings(), keys(Key.F2, Key.Up, Key.Enter), (40, 10))
    closed = await screen(picker.settings(), keys(Key.F2, Key.Escape), (40, 10))

    assert ("CPython" in opened, "Python 3.14" in upward, "CPython" in closed) == (True, True, False)


async def test_the_picker_stays_open_on_enter_when_nothing_matches() -> None:
    shown = await screen(picker.settings(), (*keys(Key.F2), *typed("zz"), *keys(Key.Enter)), (40, 10))

    assert ("nothing matches" in shown, "Python 3.15" in shown) == (True, True)


@component
def picker_in_a_parent_that_takes_its_keys() -> Div:
    picking, _ = use_state(picker.Picking(picker.PYTHON))
    nothing_reached: tuple[str, ...] = ()
    reached, set_reached = use_state(nothing_reached)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.F2):
                return picking.opened()
            case KeyPressed(key=key):
                set_reached(lambda keys: (*keys, key))
                return ()
            case _:
                return None

    return Div(
        on_input=on_input,
        children=(
            Text(content=f"reached: {' '.join(map(str, reached))}"),
            picker.picker(picking, "3.15", lambda _: None, lambda: None),
        ),
    )


async def test_the_picker_keeps_its_keys_from_its_parent_when_nothing_matches_until_it_lets_go_of_focus() -> None:
    kept = (*keys(Key.F2), *typed("zz"), *keys(Key.Down, Key.Up, Key.Enter, Key.Tab))
    steps = (*kept, *keys(Key.Escape, Key.Tab), *press(0, 0))

    shown = await screen(picker_in_a_parent_that_takes_its_keys(), steps, (40, 10))

    assert shown.splitlines()[0] == "reached: Key.Tab"


async def test_a_draggable_ignores_a_press_of_another_button() -> None:
    assert await screen(draggable.root(), press(5, 3, button=3), (40, 10)) == await screen(
        draggable.root(), (), (40, 10)
    )


async def test_the_forecast_goes_back_a_city_with_left() -> None:
    assert "Fetching Lima..." in await screen(use_effect_forecast.weather(), keys(Key.Left), (30, 4))


async def test_the_pager_pages_with_space_d_and_u() -> None:
    top = await screen(scrolling.pager(), (), (40, 10))
    paged = await screen(scrolling.pager(), keys(" "), (40, 10))
    halfway = await screen(scrolling.pager(), keys("d"), (40, 10))
    back = await screen(scrolling.pager(), keys(" ", "u", "u"), (40, 10))

    assert (paged != top, halfway not in (top, paged), back) == (True, True, top)


@component
def not_a_scroll_container() -> Div:
    return Div(on_input=scrolling.less_keys)


async def test_the_pagers_keys_do_nothing_off_a_scroll_container() -> None:
    assert await screen(not_a_scroll_container(), keys(" "), (4, 1)) == ""


async def test_the_order_forms_fields_change_with_their_keys_and_ignore_others() -> None:
    steps = [
        *keys(Key.Left, Key.Right, Key.Left),
        *keys(Key.Enter, Key.Up, Key.Up, Key.Down, "x"),
        *keys(Key.Enter, "x", Key.Space),
        *press(*focus_form.HELP_PANEL),
        *keys(Key.Right, Key.Left, Key.Left, "x"),
    ]

    shown = await screen(focus_form.order_form(), steps)

    assert [text for text in ("< Large >", "2 ▴▾", "[x]", "Tip 3/3") if text not in shown] == []


async def runs_until_it_quits(root: Component, steps: Sequence[AutopilotStep]) -> None:
    """Runs `root` headless under `steps`, which end with the app quitting itself, failing rather than hanging."""
    with nothing_attached() as (input_stream, output_stream):
        await wait_for(
            app(
                root,
                input_stream=input_stream,
                output_stream=output_stream,
                headless=True,
                dimensions=(40, 6),
                autopilot=steps,
            ),
            TIMEOUT,
        )


def shows(text: str) -> WaitFor:
    return WaitFor(lambda frame: text in frame.text(ansi=False), timeout=timedelta(seconds=TIMEOUT))


def prompts(count: int) -> WaitFor:
    """Wait until a plain shell has printed `count` prompts."""
    return WaitFor(lambda frame: frame.text(ansi=False).count("$ ") >= count, timeout=timedelta(seconds=TIMEOUT))


async def test_the_terminal_widget_quits_on_ctrl_q_and_sends_its_shell_every_other_key() -> None:
    await runs_until_it_quits(
        terminals.shell(PLAIN_SHELL),
        [prompts(1), *keys("e", "c", "h", "o", " ", "h", "i", Key.Enter), prompts(2), KeyPressed(key=Key.ControlQ)],
    )


def ignores_everything(event: InputEvent, receiver: Receiver) -> InputResponse:
    return None


async def test_a_pane_shows_its_program() -> None:
    shown = await screen(
        terminals.pane(("sh", "-c", "echo hello from the pane; sleep 30"), ignores_everything),
        [shows("hello from the pane"), KeyPressed(key="x")],
        (40, 5),
    )

    assert "hello from the pane" in shown


async def test_the_pseudoterminal_example_says_why_its_program_failed_to_start() -> None:
    shown = await screen(pseudoterminals.program(("/nonexistent/program",)), [shows("Failed to start")], (44, 15))

    assert "No such file or directory" in shown


async def test_a_slide_runs_its_command_when_shown() -> None:
    shown = await screen(commands.slide("Greetings", ("echo", "hello")), [shows("exited 0")], (40, 8))

    assert ("Greetings" in shown, "hello" in shown) == (True, True)


async def test_the_code_runner_runs_its_code_on_f5_and_ignores_other_keys() -> None:
    shown = await screen(
        commands.code_runner(), [*keys(Key.F12, Key.F5), shows("exited 0"), *keys(Key.Escape)], (60, 16)
    )

    assert "2 squared is 4" in shown


async def test_the_code_runner_stops_its_code_on_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    shown = await screen(
        commands.code_runner(), [*keys(Key.F5), shows("running"), *keys(Key.Escape), shows("cancelled")], (60, 16)
    )

    assert "cancelled" in shown


@pytest.mark.parametrize(
    ("in_a_repository", "path", "expected"),
    [
        (True, None, "Back from the log"),
        (False, None, "git log exited 128"),
        (True, "", "Couldn't start git: No such file or directory"),
    ],
)
async def test_the_log_viewer_says_how_git_log_ended(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, in_a_repository: bool, path: str | None, expected: str
) -> None:
    if not in_a_repository:
        monkeypatch.chdir(tmp_path)
    if path is not None:
        monkeypatch.setenv("PATH", path)

    assert expected in await screen(programs.log_viewer(), [*keys("x", "l")], (60, 2))


@pytest.mark.parametrize(
    ("editor", "expected"),
    [('sh -c \'printf "a = 2" > "$1"\' editor', "a = 2"), ("counterweight-no-such-editor", "a = 1")],
)
async def test_the_config_editor_reads_the_file_again_once_the_editor_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, editor: str, expected: str
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("a = 1")
    monkeypatch.setenv("VISUAL", editor)

    assert await screen(programs.config_editor(config), keys("x", "e"), (20, 1)) == expected


async def test_the_note_says_when_its_editor_fails_to_start() -> None:
    shown = await screen(programs.note(editor=("counterweight-no-such-editor",)), keys("x", "e"), (60, 8))

    assert "Couldn't start the editor: No such file or directory" in shown


@component
def runs_tests_on_t() -> Div:
    return Div(on_input=programs.run_tests_on_t, children=(Text(content="still here"),))


async def test_t_runs_the_tests_then_waits_for_enter_before_the_app_comes_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    assert await screen(runs_tests_on_t(), keys("x", "t"), (10, 1)) == "still here"


@pytest.mark.parametrize(
    ("editor", "expected"),
    [('sh -c \'printf "  Deploys  " > "$1"\' editor', "Deploys"), ("false", "Window title")],
)
async def test_the_title_editor_edits_its_draft_in_the_editor(
    monkeypatch: pytest.MonkeyPatch, editor: str, expected: str
) -> None:
    monkeypatch.setenv("VISUAL", editor)

    assert expected in (await screen(input_controls.title_editor(), keys(Key.ControlO), (62, 6))).splitlines()[1]


async def test_the_autopilot_pages_demo_records_its_chapters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    await autopilot_search.record_demo()

    assert (tmp_path / "search.cast").read_text().count('"m"') == 3


async def test_a_toolbar_button_is_selected_by_a_click() -> None:
    shown = await screen(styles_merging.toolbar(), press(28, 1), (35, 3))

    assert shown.splitlines()[0] == "╭──────╮ ╭──────╮ ╭──────╮ ┏━━━━━━┓"


async def test_a_process_row_is_selected_by_a_click() -> None:
    root = performance_process_table.root()
    clicked = await frame_of(Still("test", root, (32, 7), steps=press(4, 3)))
    moved = await frame_of(Still("test", root, (32, 7), steps=keys(Key.Down, Key.Down)))

    assert clicked.text(ansi=True) == moved.text(ansi=True)


async def test_the_picker_chooses_from_the_text_typed_with_enter_in_one_write(terminal: Terminal) -> None:
    chosen: list[str] = []

    @component
    def opened() -> Div:
        picking, _ = use_state(lambda: picker.Picking(picker.PYTHON))
        send = use_controls()

        async def type_ahead() -> None:
            send(FocusOn(picking.focus))
            os.write(terminal.keyboard, b"pypy\r")

        use_effect(type_ahead, deps=())

        def choose(name: str) -> None:
            chosen.append(name)
            send(Quit())

        return Div(children=(picker.picker(picking, "3.15", choose, lambda: None),))

    await wait_for(
        app(opened(), output_stream=io.StringIO(), input_stream=terminal.stream, dimensions=(40, 10)), TIMEOUT
    )

    assert chosen == ["PyPy"]


SKY_800 = text_bg("sky", 800).text_style.background


async def frame(root: Component, steps: Sequence[AutopilotStep], dimensions: tuple[int, int]) -> Frame:
    return await frame_of(Still("test", root, dimensions, steps))


def highlighted(shown: Frame) -> list[str]:
    """The text of each row with a cell in the pickers' highlight color."""
    return [
        "".join(cell.grapheme for cell in row).strip(" │")
        for row in shown.paint.rows()
        if any(cell.style.background == SKY_800 for cell in row)
    ]


def text_of(shown: Frame) -> str:
    return "\n".join(line.rstrip() for line in shown.text(ansi=False).splitlines())


async def test_the_combobox_recipe_fills_in_the_text_with_down_and_enter() -> None:
    shown = await frame(options.add_package(), (*typed("py"), *keys(Key.Down, Key.Enter)), (30, 7))

    assert text_of(shown).splitlines()[1:3] == [" pydantic", ""]


async def test_the_combobox_recipe_stops_at_the_last_option() -> None:
    shown = await frame(options.add_package(), (*typed("pyt"), *keys(Key.Down, Key.Down, Key.Down, Key.Down)), (30, 7))

    assert highlighted(shown) == ["pytest-asyncio"]


async def test_the_combobox_recipe_closes_on_escape_and_reopens_on_up_with_the_last_option() -> None:
    closed = await frame(options.add_package(), (*typed("py"), *keys(Key.Escape)), (30, 7))
    reopened = await frame(options.add_package(), (*typed("py"), *keys(Key.Escape, Key.Up)), (30, 7))

    assert ("mypy" in text_of(closed), highlighted(reopened)) == (False, ["pytest-asyncio"])


async def test_the_combobox_recipe_lists_every_option_on_down_in_an_empty_field() -> None:
    shown = await frame(options.add_package(), keys(Key.Down), (30, 7))

    assert highlighted(shown) == ["counterweight"]


async def test_the_palette_runs_the_command_down_moved_to() -> None:
    shown = await frame(options.palette(), (*typed("f"), *keys(Key.Down, Key.Enter)), (30, 10))

    assert "Ran: Format document" in text_of(shown)


async def test_the_palette_wraps_from_the_first_command_to_the_last() -> None:
    shown = await frame(options.palette(), keys(Key.Up, Key.Enter), (30, 10))

    assert "Ran: Split right" in text_of(shown)


@pytest.mark.parametrize(
    ("moves", "searched"),
    [((), "python"), ((Key.Down,), "python asyncio"), ((Key.Down,) * 4, "python")],
    ids=["the typed text", "the suggestion moved to", "the typed text once released past the last"],
)
async def test_the_search_box_searches(moves: tuple[str, ...], searched: str) -> None:
    shown = await frame(options.searches(), (*typed("python"), *keys(*moves, Key.Enter)), (30, 6))

    assert f"Searched: {searched}" in text_of(shown)


@pytest.mark.parametrize(
    ("steps", "line"),
    [
        (keys(Key.Tab), "$ cargo"),
        (keys(Key.Tab, Key.Tab), "$ cat"),
        (keys(*(Key.Tab,) * 6), "$ cargo"),
        (keys(Key.Tab, Key.BackTab), "$ chown"),
        ((*keys(Key.Tab), *typed(" "), *keys(Key.Tab)), "$ cargo"),
    ],
    ids=["first match", "next match", "wraps", "back", "an edit ends the cycle"],
)
async def test_tab_cycling(steps: Sequence[KeyPressed], line: str) -> None:
    shown = await frame(options.command_line(), (*typed("c"), *steps), (30, 1))

    assert text_of(shown) == f" {line}"


@pytest.mark.parametrize(
    ("steps", "line"),
    [
        (typed("git s"), "$ git status"),
        ((*typed("git s"), *keys(Key.Right), *typed("!")), "$ git status!"),
        ((*typed("git s"), *keys(Key.Left, Key.Right), *typed("!")), "$ git s!"),
    ],
    ids=["shows the rest of a history line", "right at the end accepts it", "right before the end only moves"],
)
async def test_inline_completion(steps: Sequence[KeyPressed], line: str) -> None:
    shown = await frame(options.shell_prompt(), steps, (40, 1))

    assert text_of(shown) == f" {line}"


async def test_inline_completion_reads_the_cursor_a_left_moved_before_a_render(terminal: Terminal) -> None:
    frames: list[Frame] = []

    @component
    def typed_ahead() -> Div:
        async def type_the_start() -> None:
            os.write(terminal.keyboard, b"git s")

        use_effect(type_the_start, deps=())

        # Once a render has drawn the cursor at the end, Left, Right and ! arrive in one read, before the next.
        # The prompt claims every key typed, so only the autopilot's F12 bubbles here.
        def type_the_rest(event: InputEvent, _: Receiver) -> InputResponse:
            os.write(terminal.keyboard, b"\x1b[D\x1b[C!")
            return ()

        return Div(on_input=type_the_rest, children=(options.shell_prompt(),))

    await wait_for(
        app(
            typed_ahead(),
            output_stream=io.StringIO(),
            input_stream=terminal.stream,
            dimensions=(40, 1),
            autopilot=[
                showing("git status"),
                KeyPressed(key=Key.F12),
                showing("!"),
                Screenshot(handler=frames.append),
                Quit(),
            ],
        ),
        TIMEOUT,
    )

    assert text_of(frames[-1]) == " $ git s!"


async def test_the_refreshing_rows_keep_the_highlight_on_its_row_as_a_row_appears_above_it() -> None:
    before = await frame(options.processes(), keys(Key.Down), (32, 7))
    after = await frame(options.processes(), (*keys(Key.Down), AdvanceClock(by=timedelta(seconds=4))), (32, 7))

    assert (highlighted(before), highlighted(after), "uvicorn" in text_of(after)) == (
        ["1203 nginx"],
        ["1203 nginx"],
        True,
    )


async def test_ctrl_x_stops_the_highlighted_process_and_stays() -> None:
    shown = await frame(options.processes(), keys(Key.Down, Key.ControlX), (32, 7))

    assert ("nginx" in text_of(shown), highlighted(shown)) == (False, ["2048 postgres"])


async def test_marks_count_refuse_a_worktree_with_changes_and_enter_acts_on_them() -> None:
    shown = await frame(options.worktrees(), keys(" ", Key.Down, " ", Key.Down, " ", Key.Enter), (40, 7))

    assert (text_of(shown).splitlines()[0], "Removed: feature/pickers, fix/resize" in text_of(shown)) == (
        " 2 marked",
        True,
    )


async def test_enter_with_no_marks_does_nothing() -> None:
    shown = await frame(options.worktrees(), keys(Key.Enter), (32, 7))

    assert "Removed: nothing yet" in text_of(shown)


async def test_headings_are_never_highlighted() -> None:
    steps = [*keys(*(Key.Down,) * 4)]
    down = await frame(options.pythons(), steps, (22, 10))
    up = await frame(options.pythons(), [*steps, *keys(Key.Up)], (22, 10))
    chosen = await frame(options.pythons(), [*steps, *keys(Key.Enter)], (22, 10))

    assert (highlighted(down), highlighted(up), "Python pypy3.10" in text_of(chosen)) == (
        ["pypy3.10"],
        ["3.15t"],
        True,
    )


async def test_the_preview_follows_the_highlight() -> None:
    moved = await frame(options.swatches(), keys(Key.Down, Key.Down), (30, 6))
    typed_after = await frame(options.swatches(), (*keys(Key.Down, Key.Down), *typed("i"), *keys(Key.Down)), (30, 6))

    assert (text_of(moved).splitlines()[0].split(), text_of(typed_after).splitlines()[0].split()) == (
        ["amber"],
        ["i", "indigo"],
    )


async def test_typing_into_the_refreshing_rows_narrows_them_and_up_moves_back() -> None:
    narrowed = await frame(options.processes(), typed("n"), (32, 7))
    up = await frame(options.processes(), keys(Key.Up), (32, 7))

    assert (highlighted(narrowed), highlighted(up)) == (["1203 nginx"], ["1203 nginx"])


async def test_typing_into_the_marks_narrows_the_worktrees() -> None:
    shown = await frame(options.worktrees(), typed("fix"), (32, 7))

    assert highlighted(shown) == ["fix/cursor (changes)"]


async def test_clicking_a_color_highlights_it() -> None:
    shown = await frame(options.swatches(), press(2, 3), (30, 6))

    assert text_of(shown).splitlines()[0].split() == ["amber"]
