import io
from collections.abc import Callable
from functools import partial
from typing import TextIO

import pytest

from counterweight import FullScreen
from counterweight import Inline
from counterweight._output import start_bracketed_paste
from counterweight._output import start_mouse_tracking
from counterweight._output import start_output_control
from counterweight._output import stop_bracketed_paste
from counterweight._output import stop_mouse_tracking
from counterweight._output import stop_output_control


class RecordingStream(io.StringIO):
    """A stream that records what it held each time it was flushed."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed: list[str] = []

    def flush(self) -> None:
        self.flushed.append(self.getvalue())


@pytest.mark.parametrize(
    ("switch", "expected"),
    [
        (partial(start_output_control, viewport=FullScreen()), "\x1b[?1049h\x1b[?25l\x1b[2J\x1b[22;0t"),
        (partial(stop_output_control, viewport=FullScreen()), "\x1b[?1049l\x1b[?25h\x1b[23;0t"),
        (partial(start_output_control, viewport=Inline()), "\x1b[?25l\x1b[22;0t"),
        (partial(stop_output_control, viewport=Inline()), "\x1b[?25h\x1b[23;0t"),
        (start_mouse_tracking, "\x1b[?1003h\x1b[?1006h"),
        (stop_mouse_tracking, "\x1b[?1003l\x1b[?1006l"),
        (start_bracketed_paste, "\x1b[?2004h"),
        (stop_bracketed_paste, "\x1b[?2004l"),
    ],
)
def test_terminal_mode_switch_writes_its_sequences_then_flushes(
    switch: Callable[[TextIO], None], expected: str
) -> None:
    stream = RecordingStream()

    switch(stream)

    assert stream.flushed == [expected]
