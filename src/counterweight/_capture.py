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
    Once released, it writes straight to `original`, so code that kept a reference to it,
    such as a logging handler made while it was `sys.stderr`, doesn't send lines to an app that has stopped,
    or to one that's suspended, which recaptures it when it resumes, so that code sends lines again.

    It isn't a terminal, so a library that colors its output only on a terminal writes plain text to it.
    """

    def __init__(self, original: TextIO, send: Callable[[str], None]) -> None:
        super().__init__()
        self.original = original
        self.send = send
        self.partial = ""
        self.is_released = False
        self.lock = Lock()

    def write(self, text: str) -> int:
        with self.lock:
            is_released = self.is_released
            if not is_released:
                *lines, self.partial = (self.partial + text).split("\n")
        if is_released:
            return self.original.write(text)
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

    def flush(self) -> None:
        # Closing this stream flushes it, as collecting it does, by which time `original` may be closed too.
        if self.is_released and not self.original.closed:
            self.original.flush()

    def release(self) -> str:
        """
        Stops sending lines, so later writes go straight to `original`,
        and returns the text written after the last newline, which no line has sent.
        """
        with self.lock:
            partial, self.partial = self.partial, ""
            self.is_released = True
        return partial

    def recapture(self) -> None:
        """Starts sending lines again after `release`, as an app does when it resumes from a suspension."""
        with self.lock:
            self.is_released = False


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


def resume_capturing(capture: Capture) -> None:
    """
    Replaces `sys.stdout` and `sys.stderr` with `capture`'s streams again, after `stop_capturing` put back the ones
    they replaced, so code that kept a reference to them while they were captured sends lines again.
    """
    capture.stdout.recapture()
    capture.stderr.recapture()
    sys.stdout = capture.stdout
    sys.stderr = capture.stderr


def stop_capturing(capture: Capture) -> None:
    """
    Puts back the streams `capture` replaced, and writes them the text written after the last newline,
    which no line has sent, since nothing will end it now.
    """
    sys.stdout = capture.stdout.original
    sys.stderr = capture.stderr.original
    for captured in (capture.stdout, capture.stderr):
        if partial := captured.release():
            captured.original.write(partial)
            captured.original.flush()
