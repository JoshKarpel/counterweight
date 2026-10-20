from __future__ import annotations

import json
from datetime import timedelta

from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.examples.scenes import SCENE_TIME
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.examples.scenes import frame_of
from counterweight.examples.scenes import recording_of
from counterweight.hooks import use_clock
from counterweight.hooks import use_state


@component
def typed() -> Text:
    text, set_text = use_state("")
    tick = use_clock(timedelta(seconds=1))

    def on_input(event: InputEvent, _: Receiver) -> None:
        assert isinstance(event, KeyPressed)
        set_text(lambda current: current + event.key)

    return Text(content=f"{tick.now:%H:%M:%S} {text}", on_input=on_input)


async def test_a_still_shows_its_root_after_its_steps_at_the_scene_time() -> None:
    frame = await frame_of(Still("typed", typed(), (14, 1), steps=[KeyPressed(key="h"), KeyPressed(key="i")]))

    assert frame.text(ansi=False).rstrip() == f"{SCENE_TIME:%H:%M:%S} hi"


async def test_a_demo_records_its_steps_with_their_input_timed_by_its_clock() -> None:
    recording = await recording_of(
        Demo("typed", typed(), (14, 1), steps=[AdvanceClock(by=timedelta(seconds=3)), KeyPressed(key="h")])
    )

    header, *events = (json.loads(line) for line in recording.splitlines())
    typed_at = [
        (sum(interval for interval, *_ in events[: i + 1]), data)
        for i, (_, code, data) in enumerate(events)
        if code == "i"
    ]
    assert (header["timestamp"], typed_at) == (int(SCENE_TIME.timestamp()), [(3.0, "h")])
