"""
A recording of a multiplexer laid out like `examples/multiplexer.py`, with a prefix key that moves focus between panes,
whose panes replay output written ahead of time, as a shell running pytest and as top,
since a real program's output doesn't come out the same on every run.
"""

import asyncio
import random
from datetime import timedelta

from more_itertools import last

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import FocusNext
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Screen
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.painters.terminal import ScreenView
from counterweight.styles.utilities import *
from docs.examples.emulator_replay import TICK
from docs.examples.emulator_replay import RecordedOutput
from docs.examples.emulator_replay import goto
from docs.examples.emulator_replay import replay
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec

COLUMNS, ROWS = 38, 17
PROMPT = "\x1b[1;32m~/project\x1b[0m $ "


def shell_session() -> RecordedOutput:
    """A shell that runs pytest, which prints a dot for each test as it passes."""
    chunks: list[tuple[timedelta, str]] = [(timedelta(), "\x1b]0;~/project\x07" + PROMPT)]
    at = timedelta(milliseconds=500)
    for character in "pytest":
        chunks.append((at, character))
        at += TICK
    chunks += [
        (at, "\r\n\x1b]0;pytest\x07"),
        (at + 2 * TICK, "\x1b[1m====== test session starts ======\x1b[0m\r\ncollected 24 items\r\n\r\n"),
    ]
    at += 4 * TICK
    done = 0
    for file, count in (("test_app.py", 8), ("test_cli.py", 6), ("test_io.py", 10)):
        chunks.append((at, f"tests/{file} "))
        for _ in range(count):
            at += TICK
            chunks.append((at, "\x1b[32m.\x1b[0m"))
        done += count
        padding = COLUMNS - len(f"tests/{file} ") - count - 6
        chunks.append((at, " " * padding + f"\x1b[32m[{100 * done // 24:>3}%]\x1b[0m\r\n"))
    chunks += [
        (at + 2 * TICK, "\r\n\x1b[32m====== \x1b[1m24 passed\x1b[22m in 2.41s ======\x1b[0m\r\n"),
        (at + 3 * TICK, "\x1b]0;~/project\x07" + PROMPT),
    ]
    return [(at, text.encode()) for at, text in chunks]


def bar(label: str, user: int, system: int, width: int) -> str:
    """A meter as top draws one: green for user time and red for system time, out of `width` cells."""
    used, kernel = user * width // 100, system * width // 100
    percent = f"{user + system}%"
    return (
        f"\x1b[36m{label}\x1b[0m["
        + f"\x1b[32m{'|' * used}\x1b[31m{'|' * kernel}\x1b[0m"
        + " " * (width - used - kernel - len(percent))
        + f"{percent}]"
    )


PROGRAMS = ("python", "node", "postgres", "redis-server", "sshd", "systemd", "cron", "bash", "top")


def top_session(seconds: int) -> RecordedOutput:
    """Top on the alternate screen, redrawing every second with numbers that move."""
    rng = random.Random(1)
    chunks = [(timedelta(), "\x1b]0;top\x07\x1b[?1049h\x1b[?25l")]
    for second in range(seconds):
        cpus = [(rng.randrange(5, 60), rng.randrange(2, 15)) for _ in range(2)]
        processes = sorted(
            ((rng.randrange(300, 9000), program, rng.randrange(0, 400) / 10) for program in PROGRAMS),
            key=lambda process: -process[2],
        )
        lines = [
            f"top - 15:09:{26 + second:02} up 3 days, load 0.{40 + second}",
            "Tasks: \x1b[1m112\x1b[0m total, \x1b[1m2\x1b[0m running",
            *(bar(f"Cpu{index} ", user, system, COLUMNS - 8) for index, (user, system) in enumerate(cpus)),
            bar("Mem  ", 31 + second % 3, 12, COLUMNS - 8),
            "",
            "\x1b[30;42m" + "  PID USER   %CPU COMMAND".ljust(COLUMNS) + "\x1b[0m",
            *(f"{pid:>5} dev   {cpu:>5.1f} {program}" for pid, program, cpu in processes),
        ]
        chunks.append(
            (
                second * timedelta(seconds=1),
                "".join(goto(row, 1) + line + "\x1b[K" for row, line in enumerate(lines, start=1)),
            )
        )
    return [(at, text.encode()) for at, text in chunks]


SHELL = replay(shell_session(), COLUMNS, ROWS)
TOP = replay(top_session(seconds=10), COLUMNS, ROWS)


@component
def pane(number: int, screens: tuple[tuple[timedelta, Screen], ...], prefix: InputHandler, auto_focus: bool) -> Div:
    focus = use_focus(auto_focus=auto_focus)
    elapsed = use_clock(TICK).since_mount
    screen = last((screen for at, screen in screens if at <= elapsed), screens[0][1])
    color = "emerald" if focus.is_focused else "slate"

    return Div(
        style=fill(1) | border | border_lightrounded | border_color(color, 400 if focus.is_focused else 600),
        on_input=prefix,
        children=(
            Canvas(painter=ScreenView(screen, show_cursor=focus.is_focused), style=fill(1)),
            Div(
                style=position_absolute | inset_top(-1) | inset_left(1) | inset_right(1) | clip_to_border,
                children=(
                    Text(
                        content=f" Pane #{number} · {screen.title} ",
                        style=text_wrap_none | text_color(color, 400),
                    ),
                ),
            ),
        ),
    )


def key_hints(is_armed: bool) -> tuple[Chunk, ...]:
    mode = Chunk(
        content=" PREFIX " if is_armed else " Ctrl b ",
        style=CellStyle(foreground=slate_900, background=emerald_400 if is_armed else slate_400, bold=True),
    )
    key = CellStyle(foreground=amber_400 if is_armed else slate_500, background=slate_700, bold=is_armed)
    label = CellStyle(foreground=slate_100 if is_armed else slate_500, background=slate_700)
    return (mode, Chunk.space(), Chunk(content=" <o> ", style=key), Chunk(content="NEXT PANE ", style=label))


@component
def multiplexer() -> Div:
    is_armed = use_ref(False)
    shows_armed, set_shows_armed = use_state(False)

    def arm(value: bool) -> None:
        is_armed.current = value
        set_shows_armed(value)

    def prefix(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlB) if not is_armed.current:
                arm(True)
                return ()
            case KeyPressed(key="o") if is_armed.current:
                arm(False)
                return FocusNext()
            case _:
                return None

    return Div(
        style=col | full,
        on_input=prefix,
        children=(
            Div(
                style=row | grow(1),
                children=(
                    pane(1, SHELL, prefix, auto_focus=True).with_key("1"),
                    pane(2, TOP, prefix, auto_focus=False).with_key("2"),
                ),
            ),
            Text(content=key_hints(shows_armed), style=text_wrap_none),
        ),
    )


def at_ticks(keys: dict[int, KeyPressed], ticks: int) -> list[AdvanceClock | KeyPressed]:
    """A tick of the clock at a time for `ticks` ticks, with each of `keys` pressed after its tick."""
    steps: list[AdvanceClock | KeyPressed] = []
    for tick in range(1, ticks + 1):
        steps.append(AdvanceClock(by=TICK))
        if key := keys.get(tick):
            steps.append(key)
    return steps


SWITCHES = {
    55: KeyPressed(key=Key.ControlB),
    60: KeyPressed(key="o"),
    80: KeyPressed(key=Key.ControlB),
    85: KeyPressed(key="o"),
}

SCREENSHOTS: list[ScreenshotSpec] = []

CASTS = [CastSpec(multiplexer(), "terminals-multiplexer", (80, 20), steps=at_ticks(SWITCHES, ticks=100))]


if __name__ == "__main__":
    asyncio.run(app(multiplexer()))
