"""
Every example's stills and demos render to the screenshots and recordings committed in `docs/assets/`,
so a change that alters what an example shows, down to a color, fails here rather than only changing an asset.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from counterweight import app
from counterweight._output import Frame
from counterweight.autopilot import AutopilotStep
from counterweight.clock import FrozenClock
from counterweight.components import Component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseUp
from counterweight.examples import gallery
from counterweight.examples.catalog import examples
from counterweight.examples.scenes import SCENE_TIME
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.examples.scenes import nothing_attached
from counterweight.examples.scenes import recording_of
from counterweight.geometry import Position
from counterweight.keys import Key

ASSETS = Path(__file__).parent.parent.parent / "docs" / "assets"

REGENERATE = "if the change is meant, regenerate the assets with `uv run python -m docs.generate_screenshots`"

CATALOG = examples()

# The gallery isn't an example, so the catalog doesn't list it, but its scenes are in the docs as the examples' are.
STILLS = [*(still for example in CATALOG for still in example.stills), *gallery.STILLS]
DEMOS = [*(demo for example in CATALOG for demo in example.demos), *gallery.DEMOS]


@pytest.mark.parametrize("still", STILLS, ids=lambda still: still.name)
async def test_a_still_shows_what_its_screenshot_does(still: Still) -> None:
    frame = await frame_of(still)

    assert frame.text(ansi=False) + "\n" == (ASSETS / f"{still.name}.txt").read_text(), REGENERATE
    assert frame.svg() + "\n" == (ASSETS / f"{still.name}.svg").read_text(), REGENERATE


@pytest.mark.parametrize("demo", DEMOS, ids=lambda demo: demo.name)
async def test_a_demo_records_what_its_recording_does(demo: Demo) -> None:
    assert await recording_of(demo) == (ASSETS / f"{demo.name}.cast").read_text(), REGENERATE


ROOTS = [pytest.param(root, id=example.root_name(root)) for example in CATALOG for root in example.roots]

UNBOUND: list[AutopilotStep] = [
    KeyPressed(key=Key.F12),
    KeyPressed(key="alt+z"),
    MouseMoved(absolute=Position(x=0, y=0), button=None),
    MouseDown(absolute=Position(x=0, y=0), button=3),
    MouseUp(absolute=Position(x=0, y=0), button=3),
    MouseScrolledRight(absolute=Position(x=0, y=0)),
]


@pytest.mark.parametrize("root", ROOTS)
async def test_every_root_runs_and_ignores_input_it_does_not_bind(root: Callable[[], Component]) -> None:
    frames: list[Frame] = []
    with nothing_attached() as (input_stream, output_stream):
        await app(
            root(),
            input_stream=input_stream,
            output_stream=output_stream,
            headless=True,
            dimensions=(80, 24),
            autopilot=[*UNBOUND, Screenshot(handler=frames.append), Quit()],
            check_purity=True,
            clock=FrozenClock(SCENE_TIME),
        )

    assert len(frames) == 1
