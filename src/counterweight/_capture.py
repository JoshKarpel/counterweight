"""
Catching what the app's code writes to `sys.stdout` and `sys.stderr` while it runs,
which would otherwise land in the middle of what it draws, so the render loop prints it as finished output instead.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import TextIO

from counterweight.controls import PrintStream


class CapturedLines(io.TextIOBase):
    """
    A stream that hands each line written to it, without its newline, to `send`, from whichever thread wrote it,
    and holds the text after the last newline until the next write ends it.

    It isn't a terminal, so a library that colors its output only on a terminal writes plain text to it.
    """

    def __init__(self, original: TextIO, send: Callable[[str], None]) -> None:
        super().__init__()
        self.original = original
        self.send = send
        self.partial = ""
        self.lock = Lock()

    def write(self, text: str) -> int:
        with self.lock:
            *lines, self.partial = (self.partial + text).split("\n")
        for line in lines:
            self.send(line)
        return len(text)

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return self.original.encoding

    def take_partial(self) -> str:
        """The text written after the last newline, which no line has sent, leaving none held."""
        with self.lock:
            partial, self.partial = self.partial, ""
        return partial


@dataclass(frozen=True, slots=True)
class Capture:
    """The streams that replaced `sys.stdout` and `sys.stderr`, which hold the streams they replaced."""

    stdout: CapturedLines
    stderr: CapturedLines


def start_capturing(send: Callable[[str, PrintStream], None]) -> Capture:
    """Replaces `sys.stdout` and `sys.stderr` with streams that hand each line written to them to `send`."""
    capture = Capture(
        stdout=CapturedLines(sys.stdout, lambda line: send(line, "stdout")),
        stderr=CapturedLines(sys.stderr, lambda line: send(line, "stderr")),
    )
    sys.stdout = capture.stdout
    sys.stderr = capture.stderr
    return capture


def stop_capturing(capture: Capture) -> None:
    """
    Puts back the streams `capture` replaced, and writes them the text written after the last newline,
    which no line has sent, since nothing will end it now.
    """
    sys.stdout = capture.stdout.original
    sys.stderr = capture.stderr.original
    for captured in (capture.stdout, capture.stderr):
        if partial := captured.take_partial():
            captured.original.write(partial)
            captured.original.flush()
