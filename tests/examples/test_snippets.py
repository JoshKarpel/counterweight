"""
What the docs' snippets do beyond what their stills and demos show, such as the keys they ignore,
and the components their pages show without a scene of their own.
"""

from __future__ import annotations

from asyncio import wait_for
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

import pytest

from counterweight import app
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import WaitFor
from counterweight.components import Component
from counterweight.components import component
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
from counterweight.examples.snippets import input_controls
from counterweight.examples.snippets import input_handlers
from counterweight.examples.snippets import picker
from counterweight.examples.snippets import prefix_keys
from counterweight.examples.snippets import programs
from counterweight.examples.snippets import scrolling
from counterweight.examples.snippets import terminals
from counterweight.examples.snippets import text_input
from counterweight.examples.snippets import use_controls_first_error
from counterweight.examples.snippets import use_effect_forecast
from counterweight.examples.snippets.terminals import PLAIN_SHELL
from counterweight.geometry import Position
from counterweight.keys import Key
from tests.rendering import TIMEOUT


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


async def test_the_picker_chooses_upward_and_closes_on_escape() -> None:
    opened = await screen(picker.settings(), keys(Key.F2), (40, 10))
    upward = await screen(picker.settings(), keys(Key.F2, Key.Up, Key.Enter), (40, 10))
    closed = await screen(picker.settings(), keys(Key.F2, Key.Escape), (40, 10))

    assert ("CPython" in opened, "Python 3.14" in upward, "CPython" in closed) == (True, True, False)


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
