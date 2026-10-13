import io
import os
import sys
from asyncio import CancelledError, Event, create_task, get_running_loop, wait_for
from signal import SIGINT

import pytest

from counterweight.cli import SIGINT_EXIT, _check_input, main
from counterweight.constants import PACKAGE_NAME
from tests.terminal import Terminal

TIMEOUT = 5

WAITING = "Waiting for input (press ctrl+c to exit)...\n"


class Output(io.StringIO):
    """Output that signals when a line other than the waiting prompt has been printed."""

    def __init__(self) -> None:
        super().__init__()
        self.printed_input = Event()

    def write(self, text: str) -> int:
        if text.startswith("KeyPressed"):
            self.printed_input.set()
        return super().write(text)


@pytest.mark.parametrize(
    ("mouse", "mouse_on", "mouse_off"),
    [
        (False, "", ""),
        (True, "\x1b[?1003h\x1b[?1006h", "\x1b[?1003l\x1b[?1006l"),
    ],
)
async def test_check_input_prints_each_input_until_cancelled_then_stops_reading_it_and_restores_it(
    terminal: Terminal, mouse: bool, mouse_on: str, mouse_off: str
) -> None:
    before = terminal.settings()
    output = Output()

    task = create_task(_check_input(mouse=mouse, input_stream=terminal.stream, output_stream=output))
    os.write(terminal.keyboard, b"q")
    await wait_for(output.printed_input.wait(), TIMEOUT)
    task.cancel()
    with pytest.raises(CancelledError):
        await task

    assert output.getvalue() == f"{mouse_on}{WAITING}KeyPressed(key='q')\n{WAITING}{mouse_off}"
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

    with pytest.raises(SystemExit) as exit:
        main()

    assert (exit.value.code, output.getvalue()) == (SIGINT_EXIT, WAITING)
