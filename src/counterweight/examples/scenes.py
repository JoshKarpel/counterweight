"""
What an example's screenshots and recordings show, as values with nothing about files in them,
which an example module lists in its `STILLS` and `DEMOS`.

`frame_of` and `recording_of` render one headless from a frozen time, checking its components are pure,
which the docs tooling saves under its `name` in `docs/assets/`, and the tests compare with what's saved there.
Being values is what lets them be enumerated without running them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TextIO

from more_itertools import one

from counterweight._app import app
from counterweight._output import Frame
from counterweight._viewports import FullScreen
from counterweight._viewports import Inline
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.clock import FrozenClock
from counterweight.components import Component
from counterweight.controls import Quit
from counterweight.controls import Screenshot


@dataclass(frozen=True, slots=True)
class Still:
    """
    What `root` shows at `dimensions` after `steps`, which the docs save as a screenshot, `<name>.svg`,
    with a plain-text copy beside it as `<name>.txt`.

    The app's clock is frozen, so an `AdvanceClock` among the steps is the only way time passes
    that comes out the same on every run.
    The screenshot shows everything the app's terminal holds, so an `Inline` app's shows what it printed above its region,
    whichever of its streams it printed to.
    """

    name: str
    root: Component
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep] = ()
    viewport: FullScreen | Inline = FullScreen()


@dataclass(frozen=True, slots=True)
class Demo:
    """
    `root` at `dimensions` as `steps` drive it, which the docs save as a recording, `<name>.cast`,
    with its input, so the player can show the keys as they're pressed.

    The app's clock is frozen, so the `AdvanceClock`s among the steps are the time that passes in the recording,
    which comes out the same on every run as long as no step waits in real time.
    """

    name: str
    root: Component
    dimensions: tuple[int, int]
    steps: Sequence[AutopilotStep]
    viewport: FullScreen | Inline = FullScreen()


SCENE_TIME = datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)
"""When every still is taken, and every demo starts, so a still of a clock doesn't change with each run."""


async def frame_of(still: Still) -> Frame:
    """The frame `still` shows, rendered headless at `SCENE_TIME` with its components checked for purity."""
    frames: list[Frame] = []
    with nothing_attached() as (input_stream, output_stream):
        await app(
            still.root,
            input_stream=input_stream,
            output_stream=output_stream,
            stdout=output_stream,
            stderr=output_stream,
            headless=True,
            dimensions=still.dimensions,
            autopilot=[*still.steps, Screenshot(handler=frames.append, include_scrollback=True), Quit()],
            check_purity=True,
            clock=FrozenClock(SCENE_TIME),
            viewport=still.viewport,
        )
    return one(frames)


async def recording_of(demo: Demo) -> str:
    """The asciicast of `demo`, with its input, recorded headless from `SCENE_TIME` with its components checked for purity."""
    with TemporaryDirectory() as scratch, nothing_attached() as (input_stream, output_stream):
        path = Path(scratch) / "demo.cast"
        await app(
            demo.root,
            input_stream=input_stream,
            output_stream=output_stream,
            stdout=output_stream,
            stderr=output_stream,
            headless=True,
            dimensions=demo.dimensions,
            autopilot=[*demo.steps, Quit()],
            check_purity=True,
            clock=FrozenClock(SCENE_TIME),
            recording=Recording(path, input=True),
            viewport=demo.viewport,
        )
        return path.read_text()


@contextmanager
def nothing_attached() -> Iterator[tuple[TextIO, TextIO]]:
    """
    Streams to give a headless app, so a program a scene suspends it to run, such as a stand-in editor,
    reads and writes `/dev/null` rather than whatever the process rendering the scene was started with.
    """
    with Path(os.devnull).open() as input_stream, Path(os.devnull).open("w") as output_stream:
        yield input_stream, output_stream
