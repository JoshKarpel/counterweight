import io
import os
import sys
from asyncio import CancelledError
from asyncio import Event
from asyncio import create_task
from asyncio import get_running_loop
from asyncio import wait_for
from signal import SIGINT

import pytest

from counterweight._cli import SIGINT_EXIT
from counterweight._cli import _check_input
from counterweight._cli import main
from counterweight._constants import PACKAGE_NAME
from tests.terminal import Terminal

TIMEOUT = 5

WAITING = "Waiting for input (press ctrl+c to exit)...\n"


class Output(io.StringIO):
    """Output that signals when an input has been printed."""

    def __init__(self) -> None:
        super().__init__()
        self.printed_input = Event()

    def write(self, text: str) -> int:
        if text.endswith(")\n"):
            self.printed_input.set()
        return super().write(text)


PASTE_ON = "\x1b[?2004h"
PASTE_OFF = "\x1b[?2004l"


@pytest.mark.parametrize(
    ("mouse", "mouse_on", "mouse_off"),
    [
        (False, "", ""),
        (True, "\x1b[?1003h\x1b[?1006h", "\x1b[?1003l\x1b[?1006l"),
    ],
)
@pytest.mark.parametrize(
    ("typed", "printed"),
    [
        (b"q", "KeyPressed(key='q')"),
        (b"\x1b[200~hi\x1b[201~", "Pasted(text='hi')"),
    ],
)
async def test_check_input_prints_each_input_until_cancelled_then_stops_reading_it_and_restores_it(
    terminal: Terminal, mouse: bool, mouse_on: str, mouse_off: str, typed: bytes, printed: str
) -> None:
    before = terminal.settings()
    output = Output()

    task = create_task(_check_input(mouse=mouse, input_stream=terminal.stream, output_stream=output))
    os.write(terminal.keyboard, typed)
    await wait_for(output.printed_input.wait(), TIMEOUT)
    task.cancel()
    with pytest.raises(CancelledError):
        await task

    assert output.getvalue() == f"{PASTE_ON}{mouse_on}{WAITING}{printed}\n{WAITING}{PASTE_OFF}{mouse_off}"
    assert terminal.settings() == before
    assert not get_running_loop().remove_reader(terminal.stream.fileno())


class InterruptedOutput(io.StringIO):
    """Output that interrupts the process, as ctrl+c would, whenever anything is written to it."""

    def write(self, text: str) -> int:
        os.kill(os.getpid(), SIGINT)
        return super().write(text)


def test_check_input_exits_like_sigint_when_interrupted(terminal: Terminal, monkeypatch: pytest.MonkeyPatch) -> None:
    output = InterruptedOutput()
    monkeypatch.setattr(sys, "argv", [PACKAGE_NAME, "check-input"])
    monkeypatch.setattr(sys, "stdin", terminal.stream)
    monkeypatch.setattr(sys, "stdout", output)

    with pytest.raises(SystemExit) as exited:
        main()

    assert (exited.value.code, output.getvalue()) == (SIGINT_EXIT, PASTE_ON)
