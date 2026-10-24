"""
`dashboard`, with the frame counter holding its tick in its own state and stepping it from its own key handler.

Nothing above the counter holds state, so only the counter's state changes each frame:
compared with `dashboard`, this measures what skipping the components whose state didn't change saves.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import timedelta
from time import perf_counter_ns

from benchmarks.dashboard import WORKLOAD as DASHBOARD
from benchmarks.dashboard import frame_text
from benchmarks.dashboard import layout
from benchmarks.dashboard import metric_card
from counterweight import FullScreen
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_state


@dataclass(frozen=True, slots=True)
class LocalDashboard:
    """A `Runnable` without a model, since the root holds no state."""

    name: str
    description: str
    dimensions: tuple[int, int]
    interjections: Mapping[int, tuple[AnyEvent | AnyControl, ...]] = field(default_factory=dict)
    cycled_interjections: tuple[AnyEvent | AnyControl, ...] = ()
    step_key: str = "n"
    viewport: FullScreen = FullScreen()

    @component
    def root(self, key_press_times: list[int]) -> Div:
        """A root component whose key handler only appends the time to `key_press_times`; the counter steps itself."""

        def on_input(event: InputEvent, _: Receiver) -> None:
            if isinstance(event, KeyPressed):
                key_press_times.append(perf_counter_ns())

        return replace(layout(key_frame_counter(), metric_card), on_input=on_input)

    @component
    def live_root(self, frame_interval: timedelta) -> Div:
        """A root component whose counter steps itself every `frame_interval`."""
        return layout(timed_frame_counter(frame_interval), metric_card)


@component
def key_frame_counter() -> Text:
    # Focused so keys reach it, and returning None so each key still bubbles to the root that times it.
    use_focus(auto_focus=True)
    tick, set_tick = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> None:
        if isinstance(event, KeyPressed):
            set_tick(lambda previous: previous + 1)

    return replace(frame_text(tick), on_input=on_input)


@component
def timed_frame_counter(frame_interval: timedelta) -> Text:
    return frame_text(use_clock(frame_interval).since_mount // frame_interval)


WORKLOAD = LocalDashboard(
    name="dashboard-local",
    description=__doc__ or "",
    dimensions=DASHBOARD.dimensions,
)
