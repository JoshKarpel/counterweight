"""What the apps do beyond what their stills and demos show."""

from __future__ import annotations

from asyncio import wait_for
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from counterweight import app
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import WaitFor
from counterweight.components import Component
from counterweight.controls import AdvanceClock
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.examples.apps import chat
from counterweight.examples.apps import markdown_viewer
from counterweight.examples.apps import multiplexer
from counterweight.examples.apps import slides
from counterweight.examples.apps import wordle
from counterweight.examples.scenes import SCENE_TIME
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.examples.scenes import nothing_attached
from counterweight.geometry import Position
from counterweight.keys import Key
from tests.rendering import TIMEOUT


async def screen(root: Component, steps: Sequence[AutopilotStep] = (), dimensions: tuple[int, int] = (80, 24)) -> str:
    """The text `root` shows after `steps`, rendered as a still is."""
    frame = await frame_of(Still("test", root, dimensions, steps))
    return "\n".join(line.rstrip() for line in frame.text(ansi=False).splitlines())


def keys(*names: str) -> list[KeyPressed]:
    return [KeyPressed(key=name) for name in names]


def typed(text: str) -> list[KeyPressed]:
    return keys(*text)


def click_on(text: str, shown: str) -> list[MouseDown | MouseUp]:
    """A click on the first place `shown`, a screen's text, shows `text`."""
    row, line = next((row, line) for row, line in enumerate(shown.splitlines()) if text in line)
    at = Position(x=line.index(text), y=row)
    return [MouseDown(absolute=at, button=1), MouseUp(absolute=at, button=1)]


def shows(text: str) -> WaitFor:
    return WaitFor(lambda frame: text in frame.text(ansi=False), timeout=timedelta(seconds=TIMEOUT))


async def runs_until_it_quits(root: Component, steps: Sequence[AutopilotStep]) -> None:
    """Runs `root` headless under `steps`, after which the app quits itself, failing rather than hanging."""
    with nothing_attached() as (input_stream, output_stream):
        await wait_for(
            app(
                root,
                input_stream=input_stream,
                output_stream=output_stream,
                headless=True,
                dimensions=(80, 12),
                autopilot=steps,
            ),
            TIMEOUT,
        )


# The chat


def test_a_blank_draft_is_not_sent() -> None:
    blank = chat.Chat(messages=(), draft="  \n", reply=None)

    assert blank.sent() is blank


def test_a_draft_is_not_sent_while_the_bot_is_replying() -> None:
    replying = replace(chat.Chat(messages=(), draft="Hi", reply=None).sent(), draft="Again")

    assert replying.sent() is replying


async def test_ctrl_up_scrolls_the_transcript_from_the_prompt_and_ctrl_down_scrolls_back() -> None:
    asked: list[AutopilotStep] = [
        Pasted(text="Which sort should I use?"),
        KeyPressed(key=Key.Enter),
        AdvanceClock(by=timedelta(seconds=9)),
    ]
    latest = await screen(chat.root(), asked, (60, 12))

    scrolled_up = await screen(chat.root(), [*asked, KeyPressed(key=Key.ControlUp)], (60, 12))
    scrolled_back = await screen(
        chat.root(), [*asked, KeyPressed(key=Key.ControlUp), KeyPressed(key=Key.ControlDown)], (60, 12)
    )

    assert (scrolled_up != latest, scrolled_back) == (True, latest)


# The Markdown viewer


READ = WaitFor(lambda frame: "Reading..." not in frame.text(ansi=False), timeout=timedelta(seconds=TIMEOUT))


async def test_the_viewer_says_so_when_a_directory_has_no_markdown(tmp_path: Path) -> None:
    steps: list[AutopilotStep] = [READ, *keys(Key.Down)]

    assert "No Markdown files here." in await screen(markdown_viewer.root(directory=tmp_path), steps)


async def test_the_viewer_leaves_out_a_directory_whose_name_ends_in_md(tmp_path: Path) -> None:
    (tmp_path / "notes.md").mkdir()
    (tmp_path / "notes.md" / "inside.md").write_text("# Inside\n")

    shown = await screen(markdown_viewer.root(directory=tmp_path), [READ])

    assert "▸ notes.md/" in shown


async def test_the_viewers_tree_moves_its_cursor_with_up_home_and_end_and_opens_with_right() -> None:
    steps: list[AutopilotStep] = [
        markdown_viewer.READ_SAMPLES,
        *keys(Key.End, Key.Up, Key.Home, Key.Right, Key.Down, Key.Right),
    ]

    shown = await screen(markdown_viewer.root(directory=markdown_viewer.SAMPLES), steps, (100, 20))

    assert ("▾ blocks/" in shown, "blocks/alerts.md" in shown) == (True, True)


async def test_tab_moves_focus_from_the_tree_so_its_keys_no_longer_move_the_cursor() -> None:
    steps: list[AutopilotStep] = [markdown_viewer.READ_SAMPLES, *keys(Key.Tab, Key.Down, Key.Enter)]

    shown = await screen(markdown_viewer.root(directory=markdown_viewer.SAMPLES), steps, (100, 20))

    assert "▸ extensions/" in shown


async def test_left_closes_a_directory_and_moves_from_a_file_to_its_directory() -> None:
    steps: list[AutopilotStep] = [
        markdown_viewer.READ_SAMPLES,
        *keys(Key.Right, Key.Down, Key.Left, Key.Left, Key.Down),
    ]

    shown = await screen(markdown_viewer.root(directory=markdown_viewer.SAMPLES), steps, (100, 20))

    assert ("▸ blocks/" in shown, "alerts.md" in shown) == (True, False)


async def test_a_click_on_a_directory_opens_it_and_a_click_on_a_file_shows_it() -> None:
    root = markdown_viewer.root(directory=markdown_viewer.SAMPLES)
    read = markdown_viewer.READ_SAMPLES
    before = await screen(root, [read], (100, 20))
    opened = await screen(root, [read, *click_on("blocks/", before)], (100, 20))

    shown = await screen(root, [read, *click_on("blocks/", before), *click_on("tables.md", opened)], (100, 20))

    assert "blocks/tables.md" in shown.splitlines()[0]


# The multiplexer


async def test_a_pane_says_why_its_program_failed_to_start() -> None:
    shown = await screen(multiplexer.root(command=("counterweight-no-such-program",)), [shows("failed")])

    assert "failed to start: No such file or directory" in shown


async def test_the_multiplexer_closes_a_pane_whose_program_exits_and_quits_with_its_last_pane() -> None:
    await runs_until_it_quits(multiplexer.root(command=("sh", "-c", "exit 0")), [])


async def test_a_pane_whose_program_exits_while_another_is_focused_closes_without_moving_focus() -> None:
    await runs_until_it_quits(multiplexer.root(command=("sleep", "0.5")), [KeyPressed(key="alt+n")])


async def test_alt_keys_move_focus_between_panes_and_close_the_focused_one_until_none_are_left() -> None:
    await runs_until_it_quits(
        multiplexer.root(command=multiplexer.PLAIN_SHELL),
        [
            multiplexer.shows("$"),
            KeyPressed(key="alt+n"),
            multiplexer.shows("$", times=2),
            KeyPressed(key=Key.AltLeft),
            KeyPressed(key=Key.AltRight),
            KeyPressed(key="alt+x"),
            multiplexer.shows("Pane #1"),
            KeyPressed(key="alt+x"),
        ],
    )


# Slides


@pytest.mark.parametrize(
    ("editor", "expected"),
    [('sh -c \'printf "Notes, **edited**." > "$1"\' editor', "Notes, edited."), ("false", "Each slide runs")],
)
async def test_e_edits_the_slides_notes_in_the_editor(
    monkeypatch: pytest.MonkeyPatch, editor: str, expected: str
) -> None:
    monkeypatch.setenv("VISUAL", editor)

    assert expected in await screen(slides.root(), [slides.shows("exited 0"), KeyPressed(key="e")], (80, 18))


async def test_left_goes_back_a_slide_and_stops_at_the_first() -> None:
    shown = await screen(slides.root(), keys(Key.Right, Key.Left, Key.Left), (80, 18))

    assert "1 / 5" in shown


async def test_escape_stops_a_slides_command_and_r_runs_it_again() -> None:
    to_the_long_one: list[AutopilotStep] = [*keys(Key.Right) * 3, slides.shows("line 2")]
    stopped = await screen(slides.root(), [*to_the_long_one, KeyPressed(key=Key.Escape), shows("cancelled")], (80, 18))
    again = await screen(
        slides.root(), [*to_the_long_one, *keys(Key.Escape, "x", "r"), shows("line 60"), shows("exited 0")], (80, 18)
    )

    assert ("cancelled" in stopped, "exited 0" in again) == (True, True)


# Wordle


SOLUTION = "CRANE"


def test_a_finished_game_takes_no_more_letters_or_deletions() -> None:
    won = wordle.Board(solution=SOLUTION, submitted=(SOLUTION,))

    assert (won.typed("A"), won.deleted(), won.guessed()) == (won, won, won)


def test_a_board_clears_its_guess_and_refuses_one_not_in_the_word_list() -> None:
    board = wordle.Board(solution=SOLUTION, guess="QQQQQ")

    assert (board.guessed(), board.cleared().guess) == (board, "")


def test_six_wrong_guesses_lose() -> None:
    assert wordle.Board(solution=SOLUTION, submitted=("LASER",) * 6).outcome == "loss"


TODAY = wordle.daily_solution(SCENE_TIME.date())
WRONG = next(word for word in wordle.SOLUTION_WORDS if word != TODAY and not set(word) & set(TODAY))


async def test_guessing_todays_word_wins() -> None:
    assert f"You won! The word was {TODAY}" in await screen(
        wordle.root(), [KeyPressed(key=Key.F1), *typed(TODAY), KeyPressed(key=Key.Enter)], (100, 40)
    )


async def test_six_wrong_guesses_on_screen_lose() -> None:
    guesses = [step for _ in range(6) for step in (*typed(WRONG), KeyPressed(key=Key.Enter))]

    assert f"You lost! The word was {TODAY}" in await screen(
        wordle.root(), [KeyPressed(key=Key.F1), *guesses], (100, 40)
    )


async def test_a_guess_takes_pastes_and_backspace_and_ignores_other_keys() -> None:
    steps: list[AutopilotStep] = [
        KeyPressed(key=Key.F1),
        Pasted(text=" ab "),
        Pasted(text="1!"),
        *keys("1", "c", Key.Backspace),
    ]

    assert "┃ A ┃ ┃ B ┃ ┃   ┃" in await screen(wordle.root(), steps, (100, 40))


async def test_a_word_not_in_the_list_says_so_and_letters_known_to_be_wrong_show() -> None:
    steps = [KeyPressed(key=Key.F1), *typed(WRONG), KeyPressed(key=Key.Enter), *typed("QQQQQ")]

    assert "Not in word list" in await screen(wordle.root(), steps, (100, 40))
    assert "Guess 2 of 6" in await screen(wordle.root(), [*steps[:-5], *typed(WRONG[:1])], (100, 40))


async def test_the_on_screen_clear_and_exit_buttons_clear_the_guess_and_leave_the_game() -> None:
    playing = [KeyPressed(key=Key.F1), *typed("AB")]
    shown = await screen(wordle.root(), playing, (100, 40))

    cleared = await screen(wordle.root(), [*playing, *click_on("Clear", shown)], (100, 40))
    left = await screen(wordle.root(), [*playing, *click_on("Exit", shown)], (100, 40))

    assert ("┃ A ┃ ┃ B ┃" in cleared, "Play Daily" in left) == (False, True)


async def test_escape_leaves_a_game_and_f2_starts_a_random_one() -> None:
    shown = await screen(wordle.root(), keys(Key.F1, Key.Escape, Key.F2), (100, 40))

    assert "Guess 1 of 6" in shown
