"""
`dashboard`, with the frame counter holding its tick in its own state and stepping it from its own key handler.

Nothing above the counter holds state, so only the counter's state changes each frame:
compared with `dashboard`, this measures what skipping the components whose state didn't change saves.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from time import perf_counter_ns

from benchmarks.dashboard import WORKLOAD as DASHBOARD
from benchmarks.dashboard import frame_text, layout, metric_card
from counterweight.components import Component, component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_clock, use_state


@dataclass(frozen=True, slots=True)
class LocalDashboard:
    """A `Runnable` without a model, since the root holds no state."""

    name: str
    description: str
    dimensions: tuple[int, int]

    def root(self, key_press_times: list[int]) -> Callable[[], Component]:
        """A root component whose key handler only appends the time to `key_press_times`; the counter steps itself."""

        @component
        def dashboard_local_root() -> Div:
            def on_key(_: KeyPressed) -> None:
                key_press_times.append(perf_counter_ns())

            return replace(layout(key_frame_counter(), metric_card), on_key=on_key)

        return dashboard_local_root

    def live_root(self, frame_interval: timedelta) -> Callable[[], Component]:
        """A root component whose counter steps itself every `frame_interval`."""

        @component
        def live_dashboard_local_root() -> Div:
            return layout(timed_frame_counter(frame_interval), metric_card)

        return live_dashboard_local_root


@component
def key_frame_counter() -> Text:
    tick, set_tick = use_state(0)

    def on_key(_: KeyPressed) -> None:
        set_tick(lambda previous: previous + 1)

    return replace(frame_text(tick), on_key=on_key)


@component
def timed_frame_counter(frame_interval: timedelta) -> Text:
    return frame_text(use_clock(frame_interval).since_mount // frame_interval)


WORKLOAD = LocalDashboard(
    name="dashboard-local",
    description=__doc__ or "",
    dimensions=DASHBOARD.dimensions,
)
