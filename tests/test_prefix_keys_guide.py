"""The claim `docs/cookbook/prefix-keys.md` makes: a prefix and its key typed in one read still run the key's binding."""

from __future__ import annotations

import io
import os
from asyncio import wait_for

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles.utilities import full
from docs.examples import prefix_keys
from tests.terminal import Terminal

TIMEOUT = 5

CTRL_B = b"\x02"
CTRL_C = b"\x03"
CTRL_T = b"\x14"


async def test_a_prefix_and_its_key_in_one_read_open_a_pane_that_the_next_read_types_into(terminal: Terminal) -> None:
    frames: list[Frame] = []
    # A screenshot is of the frame before the read that requested it,
    # so each one types the next read, and the last frame shows what the read before it typed.
    reads = [b"yo" + CTRL_T, CTRL_T, CTRL_C]

    def record(frame: Frame) -> None:
        frames.append(frame)
        os.write(terminal.keyboard, reads[len(frames) - 1])

    def screenshot_on_ctrl_t(event: InputEvent, _: Receiver) -> InputResponse:
        return Screenshot(handler=record) if event == KeyPressed(key=Key.ControlT) else None

    @component
    def root() -> Div:
        return Div(style=full, on_input=screenshot_on_ctrl_t, children=(prefix_keys.root(),))

    os.write(terminal.keyboard, b"hi" + CTRL_B + b"c" + CTRL_T)

    await wait_for(app(root(), output_stream=io.StringIO(), input_stream=terminal.stream, dimensions=(60, 5)), TIMEOUT)

    assert frames[-1].text(ansi=False).splitlines()[1].split() == ["│1:", "hi", "││2:", "yo", "│"]
