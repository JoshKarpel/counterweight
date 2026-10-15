from __future__ import annotations

from asyncio import get_running_loop
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.elements import Text
from counterweight.emulator import BLANK_SCREEN
from counterweight.emulator import Screen
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.headless import EmbeddedTerminal
from counterweight.headless import use_terminal
from counterweight.headless.terminal import on_screen
from counterweight.hooks.impls import NodeKey
from counterweight.keys import Key
from counterweight.pseudoterminal import Exited
from counterweight.pseudoterminal import Running
from counterweight.pseudoterminal import Starting
from counterweight.styles.styles import Color
from tests.rendering import Mounted
from tests.rendering import mounted

CONTENT = Region(left=2, top=1, right=22, bottom=5)
RECEIVER = Receiver(
    rects=Rects(
        content=CONTENT,
        padding=CONTENT,
        border=Region(left=1, top=0, right=23, bottom=6),
        margin=Region(left=1, top=0, right=23, bottom=6),
        clip=Region(left=0, top=0, right=40, bottom=10),
        visible=CONTENT,
    ),
    is_target=True,
    focus_handle=None,
    is_focused=True,
    subtree=Subtree(key=NodeKey(3)),
    scroll=None,
)
UNFOCUSED = replace(RECEIVER, is_focused=False)


@component
def embed(argv: Sequence[str], columns: int, rows: int, terminals: list[EmbeddedTerminal], **kwargs: object) -> Text:
    terminals.append(use_terminal(argv, columns, rows, **kwargs))  # type: ignore[arg-type]
    return Text(content="")


def sh(script: str) -> tuple[str, ...]:
    return ("/bin/sh", "-c", script)


def text(screen: Screen) -> list[str]:
    return ["".join(cell.grapheme for cell in line).rstrip() for line in screen.lines]


def shows(terminals: list[EmbeddedTerminal], expected: str) -> Callable[[], bool]:
    return lambda: any(expected in line for line in text(terminals[-1].screen))


def received(screen: Screen) -> bytes:
    """The bytes a `reads` program printed, in hex, after its `ready`."""
    lines = text(screen)
    hex_lines = lines[lines.index("ready") + 1 :]
    return bytes(int(token, 16) for line in hex_lines for token in line.split())


def reads(count: int, setup: str = "") -> tuple[str, ...]:
    """A program that sets up its terminal's modes, says it's ready, then prints the next `count` bytes it reads in hex."""
    return sh(f"stty raw -echo; printf '{setup}'; echo ready; head -c {count} | od -An -tx1; sleep 10")


async def ready(m: Mounted, argv: tuple[str, ...], terminals: list[EmbeddedTerminal], columns: int = 60) -> None:
    await m.render(embed(argv, columns, 8, terminals))
    await m.wait_until(shows(terminals, "ready"))


async def bytes_received(m: Mounted, terminals: list[EmbeddedTerminal], count: int) -> bytes:
    await m.wait_until(lambda: len(received(terminals[-1].screen)) >= count)
    return received(terminals[-1].screen)


async def test_a_terminal_shows_what_its_program_draws() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("printf 'one\\r\\ntwo'; sleep 10"), 10, 3, terminals))
        await m.wait_until(shows(terminals, "two"))

    assert text(terminals[-1].screen) == ["one", "two", ""]


async def test_a_terminal_starts_blank_and_starting() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("sleep 10"), 0, 0, terminals))

    assert (terminals[0].screen, terminals[0].status) == (BLANK_SCREEN, Starting())


async def test_a_terminal_starts_its_program_once_it_has_a_size_and_at_that_size() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("stty size; sleep 10"), 0, 0, terminals))
        await m.render(embed(sh("stty size; sleep 10"), 20, 4, terminals))
        await m.wait_until(shows(terminals, "4 20"))

    assert (terminals[-1].screen.columns, terminals[-1].screen.rows) == (20, 4)


async def test_resizing_a_terminal_resizes_its_program_and_its_screen() -> None:
    terminals: list[EmbeddedTerminal] = []
    argv = sh("trap 'stty size' WINCH; echo ready; while :; do sleep 0.01; done")
    async with mounted() as m:
        await m.render(embed(argv, 20, 4, terminals))
        await m.wait_until(shows(terminals, "ready"))
        await m.render(embed(argv, 30, 6, terminals))
        await m.wait_until(shows(terminals, "6 30"))

    assert (terminals[-1].screen.columns, terminals[-1].screen.rows) == (30, 6)


async def test_a_terminal_runs_a_new_program_on_a_fresh_screen_when_its_argv_changes() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("printf '\\033[?2004hfirst'; sleep 10"), 20, 3, terminals))
        await m.wait_until(shows(terminals, "first"))
        await m.render(embed(sh("printf second; sleep 10"), 20, 3, terminals))
        await m.wait_until(shows(terminals, "second"))

    assert (text(terminals[-1].screen)[0], terminals[-1].screen.modes.bracketed_paste) == ("second", False)


async def test_a_terminal_names_the_default_colors_it_was_given_for_swapped_cells() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(
            embed(
                sh("printf '\\033[7mx'; sleep 10"),
                10,
                2,
                terminals,
                foreground=Color(1, 2, 3),
                background=Color(4, 5, 6),
            )
        )
        await m.wait_until(shows(terminals, "x"))

    style = terminals[-1].screen.lines[0][0].style
    assert (style.foreground, style.background) == (Color(4, 5, 6), Color(1, 2, 3))


async def test_a_terminal_names_the_default_colors_it_was_given_for_a_new_programs_swapped_cells() -> None:
    terminals: list[EmbeddedTerminal] = []
    colors = {"foreground": Color(1, 2, 3), "background": Color(4, 5, 6)}
    async with mounted() as m:
        await m.render(embed(sh("printf first; sleep 10"), 10, 2, terminals, **colors))
        await m.wait_until(shows(terminals, "first"))
        await m.render(embed(sh("printf '\\033[7msecond'; sleep 10"), 10, 2, terminals, **colors))
        await m.wait_until(shows(terminals, "second"))

    style = terminals[-1].screen.lines[0][0].style
    assert (style.foreground, style.background) == (Color(4, 5, 6), Color(1, 2, 3))


async def test_a_terminal_given_new_default_colors_keeps_its_screen_and_modes() -> None:
    terminals: list[EmbeddedTerminal] = []
    argv = sh("printf '\\033[?2004h\\033[7mx'; sleep 10")
    async with mounted() as m:
        await m.render(embed(argv, 10, 2, terminals, foreground=Color(1, 2, 3), background=Color(4, 5, 6)))
        await m.wait_until(shows(terminals, "x"))
        await m.render(embed(argv, 10, 2, terminals, foreground=Color(7, 8, 9), background=Color(10, 11, 12)))
        await m.wait_until(lambda: terminals[-1].screen.background == Color(10, 11, 12))

    screen = terminals[-1].screen
    style = screen.lines[0][0].style
    assert (text(screen)[0], screen.modes.bracketed_paste) == ("x", True)
    assert (style.foreground, style.background) == (Color(10, 11, 12), Color(7, 8, 9))


async def test_a_terminal_rendered_again_with_the_same_default_colors_renders_again_only_for_its_programs_output() -> (
    None
):
    terminals: list[EmbeddedTerminal] = []
    colors = {"foreground": Color(1, 2, 3), "background": Color(4, 5, 6)}
    # Several frames pass while the program sleeps, each a chance for a needless snapshot to render again.
    argv = sh("stty -echo; printf x; read line; sleep 0.2; printf y; sleep 10")
    async with mounted() as m:
        await m.render(embed(argv, 10, 2, terminals, **colors))
        await m.wait_until(shows(terminals, "x"))
        await m.render(embed(argv, 10, 2, terminals, **colors))
        renders = len(terminals)
        terminals[-1].write(b"\n")
        await m.wait_until(shows(terminals, "xy"))

    assert len(terminals) == renders + 1


async def test_a_terminal_answers_its_programs_queries() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        # Asks where the cursor is, which a terminal answers with `ESC [ 1 ; 1 R`.
        await m.render(
            embed(sh("stty raw -echo; printf '\\033[6n'; head -c 6 | od -An -tx1; sleep 10"), 40, 4, terminals)
        )
        await m.wait_until(shows(terminals, "1b 5b 31 3b 31 52"))


async def test_a_focused_terminal_sends_its_program_key_presses_and_claims_them() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(5), terminals)
        responses = [terminals[-1].on_input(KeyPressed(key=key), RECEIVER) for key in ("a", Key.Up, Key.ControlC)]
        sent = await bytes_received(m, terminals, 5)

    assert (responses, sent) == ([(), (), ()], b"a\x1b[A\x03")


async def test_a_terminal_sends_cursor_keys_as_its_program_asked() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(3, setup="\\033[?1h"), terminals)
        terminals[-1].on_input(KeyPressed(key=Key.Up), RECEIVER)
        sent = await bytes_received(m, terminals, 3)

    assert sent == b"\x1bOA"


async def test_a_focused_terminal_sends_its_program_a_paste_bracketed_as_it_asked() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(15, setup="\\033[?2004h"), terminals)
        response = terminals[-1].on_input(Pasted(text="a\nb"), RECEIVER)
        sent = await bytes_received(m, terminals, 15)

    assert (response, sent) == ((), b"\x1b[200~a\rb\x1b[201~")


@pytest.mark.parametrize("event", [KeyPressed(key="a"), Pasted(text="a")])
async def test_an_unfocused_terminal_leaves_keys_and_pastes_alone(event: InputEvent) -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

        assert terminals[-1].on_input(event, UNFOCUSED) is None


@pytest.mark.parametrize("event", [KeyPressed(key="a"), Pasted(text="a")])
async def test_a_terminal_whose_program_exited_leaves_keys_and_pastes_alone(event: InputEvent) -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("true"), 20, 4, terminals))
        await m.wait_until(lambda: isinstance(terminals[-1].status, Exited))

        assert terminals[-1].on_input(event, RECEIVER) is None


async def test_a_terminal_sends_its_program_the_mouse_events_it_asked_for_on_its_screen() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(9, setup="\\033[?1000h\\033[?1006h"), terminals)
        focus = FocusOn(terminals[-1].focus.handle)
        # The content box starts at (2, 1), so this is the screen's third column and second row.
        response = terminals[-1].on_input(MouseDown(absolute=Position(4, 2), button=1), UNFOCUSED)
        sent = await bytes_received(m, terminals, 9)

    assert (response, sent) == ((focus,), b"\x1b[<0;3;2M")


async def test_a_press_off_a_terminals_screen_only_focuses_it() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1, setup="\\033[?1000h"), terminals)

        assert terminals[-1].on_input(MouseDown(absolute=Position(1, 0), button=1), UNFOCUSED) == FocusOn(
            terminals[-1].focus.handle
        )


async def test_a_press_a_terminals_program_didnt_ask_for_only_focuses_it() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

        assert terminals[-1].on_input(MouseDown(absolute=Position(4, 2), button=1), UNFOCUSED) == FocusOn(
            terminals[-1].focus.handle
        )


async def test_a_press_on_an_unfocusable_terminal_that_its_program_didnt_ask_for_passes_on() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(reads(1), 40, 8, terminals, is_focusable=False))
        await m.wait_until(shows(terminals, "ready"))

        assert terminals[-1].on_input(MouseDown(absolute=Position(4, 2), button=1), UNFOCUSED) is None


async def test_a_wheel_a_terminals_program_didnt_ask_for_passes_on() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

        assert terminals[-1].on_input(MouseScrolledUp(absolute=Position(4, 2)), UNFOCUSED) is None


async def test_a_terminal_sends_a_drag_that_leaves_its_screen_clamped_to_its_edge() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(11, setup="\\033[?1002h\\033[?1006h"), terminals, columns=20)
        response = terminals[-1].on_input(MouseMoved(absolute=Position(30, 2), button=1), UNFOCUSED)
        sent = await bytes_received(m, terminals, 11)

    assert (response, sent) == ((None,), b"\x1b[<32;20;2M")


async def test_a_terminals_write_is_the_same_function_on_every_render() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

    assert len({id(terminal.write) for terminal in terminals}) == 1


async def test_a_terminal_reports_how_its_program_exited() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("exit 3"), 20, 4, terminals))
        await m.wait_until(lambda: isinstance(terminals[-1].status, Exited))

    assert terminals[-1].status == Exited(status=3)


async def test_a_terminals_status_is_running_while_its_program_runs() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

    assert terminals[-1].status == Running()


async def test_an_unfocused_terminals_view_hides_its_cursor() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(1), terminals)

    assert (terminals[-1].view.screen, terminals[-1].view.show_cursor) == (terminals[-1].screen, False)


async def test_a_terminals_write_sends_its_program_bytes() -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await ready(m, reads(3), terminals)
        terminals[-1].write(b"xyz")
        sent = await bytes_received(m, terminals, 3)

    assert sent == b"xyz"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [({}, "inherited given"), ({"clear_env": True}, "unset given")],
)
async def test_a_terminal_runs_its_program_with_env_over_the_apps_environment_unless_cleared(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object], expected: str
) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    terminals: list[EmbeddedTerminal] = []
    argv = sh('echo "${COUNTERWEIGHT_INHERITED-unset} $COUNTERWEIGHT_GIVEN"')
    async with mounted() as m:
        await m.render(embed(argv, 20, 2, terminals, env=frozendict(COUNTERWEIGHT_GIVEN="given"), **kwargs))
        await m.wait_until(shows(terminals, "given"))

    assert text(terminals[-1].screen)[0] == expected


async def test_a_terminal_terminates_a_program_that_ignores_hanging_up_after_its_hangup_grace(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    terminals: list[EmbeddedTerminal] = []
    # Ignores SIGHUP, and exits by itself after at least half a second, much longer than its grace.
    argv = sh(
        f"trap '' HUP; trap 'echo term >> {signals}; exit' TERM; echo ready; "
        f"i=0; while [ $i -lt 50 ]; do sleep 0.01; i=$((i+1)); done; echo exited >> {signals}"
    )
    async with mounted() as m:
        await m.render(embed(argv, 20, 4, terminals, hangup_grace=timedelta(milliseconds=50)))
        await m.wait_until(shows(terminals, "ready"))
        await m.render(Text(content="gone"))

    assert signals.read_text() == "term\n"


@pytest.mark.parametrize(("columns", "rows", "expected"), [(0, 3, (1, 3)), (3, 0, (3, 1))])
async def test_a_terminal_without_a_size_shows_a_blank_screen_one_cell_across_where_it_has_none(
    columns: int, rows: int, expected: tuple[int, int]
) -> None:
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("sleep 10"), columns, rows, terminals))
        await m.wait_until(lambda: terminals[-1].screen != BLANK_SCREEN)

    assert (terminals[-1].screen.columns, terminals[-1].screen.rows, text(terminals[-1].screen)[0]) == (*expected, "")


@pytest.mark.parametrize(("columns", "rows"), [(1, 3), (12, 1)])
async def test_a_terminal_resizes_its_screen_to_a_single_column_or_row(columns: int, rows: int) -> None:
    terminals: list[EmbeddedTerminal] = []
    argv = sh("trap 'printf x' WINCH; echo ready; while :; do sleep 0.01; done")
    async with mounted() as m:
        await m.render(embed(argv, 12, 3, terminals))
        await m.wait_until(shows(terminals, "ready"))
        await m.render(embed(argv, columns, rows, terminals))
        await m.wait_until(shows(terminals, "x"))

    assert (terminals[-1].screen.columns, terminals[-1].screen.rows) == (columns, rows)


async def test_a_terminal_snapshots_output_no_sooner_than_a_frame_after_its_last_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With the loop's clock stopped, a frame never passes, so a snapshot that waits for one never happens.
    loop = get_running_loop()
    stopped = loop.time()
    monkeypatch.setattr(loop, "time", lambda: stopped)
    terminals: list[EmbeddedTerminal] = []
    async with mounted() as m:
        await m.render(embed(sh("printf one"), 10, 2, terminals))
        await m.wait_until(lambda: isinstance(terminals[-1].status, Exited))
        held = text(terminals[-1].screen)
        monkeypatch.undo()
        await m.wait_until(shows(terminals, "one"))

    assert held == ["", ""]


async def focus_after(controls: Sequence[AnyControl], **kwargs: object) -> EmbeddedTerminal:
    """The terminal a headless app last rendered, after it handled `controls`."""
    terminals: list[EmbeddedTerminal] = []
    await app(
        embed(sh("sleep 10"), 0, 0, terminals, **kwargs),
        headless=True,
        dimensions=(20, 3),
        autopilot=(*controls, Quit()),
    )
    return terminals[-1]


@pytest.mark.parametrize(("kwargs", "expected"), [({}, False), ({"auto_focus": True}, True)])
async def test_a_terminal_takes_focus_when_it_mounts_only_if_asked_and_shows_its_cursor_while_focused(
    kwargs: Mapping[str, object], expected: bool
) -> None:
    terminal = await focus_after((), **kwargs)

    assert (terminal.focus.is_focused, terminal.view.show_cursor) == (expected, expected)


async def test_an_unfocusable_terminal_doesnt_take_focus_when_it_mounts() -> None:
    terminal = await focus_after((), auto_focus=True, is_focusable=False)

    assert not terminal.focus.is_focused


@pytest.mark.parametrize(("kwargs", "expected"), [({}, True), ({"in_focus_order": False}, False)])
async def test_a_terminal_is_in_the_focus_order_unless_asked_not_to_be(
    kwargs: Mapping[str, object], expected: bool
) -> None:
    terminal = await focus_after((FocusNext(),), **kwargs)

    assert terminal.focus.is_focused == expected


async def test_a_terminal_focuses_with_the_handle_it_is_given() -> None:
    handle = FocusHandle()

    terminal = await focus_after((FocusOn(handle),), handle=handle)

    assert (terminal.focus.handle, terminal.focus.is_focused) == (handle, True)


SCREEN = replace(BLANK_SCREEN, columns=10, rows=4)


@pytest.mark.parametrize(
    ("event", "position", "expected"),
    [
        (MouseDown(absolute=Position(0, 0), button=1), Position(9, 3), Position(9, 3)),
        (MouseDown(absolute=Position(0, 0), button=1), Position(10, 3), None),
        (MouseDown(absolute=Position(0, 0), button=1), Position(9, 4), None),
        (MouseDown(absolute=Position(0, 0), button=1), Position(-1, 0), None),
        (MouseDown(absolute=Position(0, 0), button=1), Position(0, -1), None),
        (MouseDown(absolute=Position(0, 0), button=1), Position(0, 2), Position(0, 2)),
        (MouseDown(absolute=Position(0, 0), button=1), Position(4, 0), Position(4, 0)),
        (MouseMoved(absolute=Position(0, 0), button=None), Position(10, 0), None),
        (MouseMoved(absolute=Position(0, 0), button=1), Position(12, -3), Position(9, 0)),
        (MouseMoved(absolute=Position(0, 0), button=1), Position(-2, 7), Position(0, 3)),
        (MouseUp(absolute=Position(0, 0), button=1), Position(15, 9), Position(9, 3)),
        (MouseUp(absolute=Position(0, 0), button=1), Position(3, 2), Position(3, 2)),
    ],
)
def test_on_screen_clamps_only_drags_and_releases_to_the_screen(
    event: MouseDown | MouseMoved | MouseUp, position: Position, expected: Position | None
) -> None:
    assert on_screen(event, position, SCREEN) == expected


@pytest.mark.parametrize(("columns", "rows"), [(0, 0), (0, 4), (10, 0)])
def test_on_screen_has_nowhere_to_clamp_to_on_a_screen_with_no_cells(columns: int, rows: int) -> None:
    screen = replace(BLANK_SCREEN, columns=columns, rows=rows)

    assert on_screen(MouseUp(absolute=Position(0, 0), button=1), Position(2, 1), screen) is None


@pytest.mark.parametrize(
    ("columns", "rows", "position", "expected"),
    [(1, 4, Position(5, 2), Position(0, 2)), (10, 1, Position(3, 5), Position(3, 0))],
)
def test_on_screen_clamps_to_a_screen_one_cell_across(
    columns: int, rows: int, position: Position, expected: Position
) -> None:
    screen = replace(BLANK_SCREEN, columns=columns, rows=rows)

    assert on_screen(MouseUp(absolute=Position(0, 0), button=1), position, screen) == expected
