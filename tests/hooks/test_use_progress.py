from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from counterweight._layout import NO_LAYOUTS
from counterweight._shadow import ShadowUpdate
from counterweight._shadow import until_due
from counterweight._shadow import update_shadow
from counterweight.animation import FRAME_INTERVAL
from counterweight.clock import Instant
from counterweight.components import component
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_loop
from counterweight.hooks import use_progress

MOUNTED = Instant(wall=datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC), monotonic=timedelta(seconds=7))
TWO_SECONDS = timedelta(seconds=2)


@component
def progress_text(duration: timedelta, deps: tuple[object, ...], interval: timedelta) -> Text:
    return Text(content=f"{use_progress(duration, deps, interval=interval):g}")


@component
def loop_text(period: timedelta, deps: tuple[object, ...], is_playing: bool) -> Text:
    return Text(content=f"{use_loop(period, deps, is_playing=is_playing):g}")


def progress(
    duration: timedelta = TWO_SECONDS, deps: tuple[object, ...] = (), interval: timedelta = FRAME_INTERVAL
) -> Div:
    return Div(children=(progress_text(duration, deps, interval).with_key("animated"),))


def loop(deps: tuple[object, ...] = (), is_playing: bool = True) -> Div:
    return Div(children=(loop_text(timedelta(seconds=1), deps, is_playing).with_key("animated"),))


class Renders:
    """Renders a tree at instants measured from `MOUNTED`, each from the last."""

    def __init__(self) -> None:
        self.last: ShadowUpdate | None = None

    def at(self, root: AnyElement, seconds: float) -> str:
        self.last = update_shadow(
            root,
            None if self.last is None else self.last.tree,
            NO_LAYOUTS,
            instant=MOUNTED + timedelta(seconds=seconds),
            check_purity=True,
        )
        (text,) = (node.element.content for node in self.last.tree.nodes if isinstance(node.element, Text))
        assert isinstance(text, str)
        return text

    def until_due(self, seconds: float) -> timedelta | None:
        assert self.last is not None
        return until_due(self.last.tree, MOUNTED + timedelta(seconds=seconds))


def test_progress_starts_at_zero_when_the_component_mounts() -> None:
    assert Renders().at(progress(), 0) == "0"


def test_progress_rises_with_the_time_since_it_started() -> None:
    renders = Renders()
    renders.at(progress(), 0)

    assert renders.at(progress(), 0.5) == "0.25"


def test_progress_holds_at_one_once_its_duration_has_passed() -> None:
    renders = Renders()
    renders.at(progress(), 0)

    assert renders.at(progress(), 3) == "1"


def test_progress_reads_the_clock_once_more_in_the_render_it_finishes() -> None:
    renders = Renders()
    renders.at(progress(), 0)
    renders.at(progress(), 3)

    assert renders.until_due(3.01) == timedelta(milliseconds=40)


def test_finished_progress_stops_reading_the_clock_after_its_last_reading() -> None:
    renders = Renders()
    root = progress()
    for seconds in (0, 3, 3.05):
        renders.at(root, seconds)

    assert renders.until_due(60) is None


def test_progress_starts_again_when_its_deps_change() -> None:
    renders = Renders()
    renders.at(progress(deps=(1,)), 0)
    renders.at(progress(deps=(1,)), 1)

    assert (renders.at(progress(deps=(2,)), 1.5), renders.at(progress(deps=(2,)), 2)) == ("0", "0.25")


def test_finished_progress_started_again_reads_the_clock_afresh() -> None:
    renders = Renders()
    for seconds in (0, 3, 3.05):
        renders.at(progress(deps=(1,)), seconds)

    assert (renders.at(progress(deps=(2,)), 10), renders.at(progress(deps=(2,)), 10.5)) == ("0", "0.25")


def test_progress_reads_the_clock_every_interval() -> None:
    renders = Renders()
    renders.at(progress(interval=timedelta(seconds=1)), 0)

    assert renders.until_due(0.25) == timedelta(seconds=0.75)


def test_progress_lasting_no_time_is_at_its_end_at_once() -> None:
    assert Renders().at(progress(duration=timedelta()), 0) == "1"


def test_progress_lasting_negative_time_raises() -> None:
    with pytest.raises(ValueError, match="isn't negative"):
        Renders().at(progress(duration=timedelta(seconds=-1)), 0)


def test_a_loop_is_where_the_time_since_it_started_puts_it_in_its_period() -> None:
    renders = Renders()
    renders.at(loop(), 0)

    assert renders.at(loop(), 2.25) == "0.25"


def test_a_loop_that_isnt_playing_holds_at_its_start_and_never_reads_the_clock() -> None:
    renders = Renders()

    assert (renders.at(loop(is_playing=False), 0), renders.until_due(60)) == ("0", None)


def test_a_paused_loop_holds_where_it_is() -> None:
    renders = Renders()
    renders.at(loop(), 0)
    renders.at(loop(), 0.25)

    assert renders.at(loop(is_playing=False), 0.5) == "0.25"


def test_a_loop_starts_again_when_its_deps_change() -> None:
    renders = Renders()
    renders.at(loop(deps=(1,)), 0)
    renders.at(loop(deps=(1,)), 2.1)

    assert (renders.at(loop(deps=(2,)), 2.25), renders.at(loop(deps=(2,)), 2.5)) == ("0", "0.25")


def test_a_loop_mounted_paused_starts_from_zero_when_it_plays() -> None:
    renders = Renders()
    renders.at(loop(is_playing=False), 0)

    assert (renders.at(loop(), 2.5), renders.at(loop(), 2.75)) == ("0", "0.25")


def test_a_loop_restarted_while_paused_holds_at_zero_and_starts_when_it_plays() -> None:
    renders = Renders()
    renders.at(loop(deps=(1,)), 0)
    renders.at(loop(deps=(1,), is_playing=False), 0.25)

    assert (
        renders.at(loop(deps=(2,), is_playing=False), 1.5),
        renders.at(loop(deps=(2,)), 3.5),
        renders.at(loop(deps=(2,)), 3.75),
    ) == ("0", "0", "0.25")


def test_a_loop_whose_deps_change_and_change_back_while_paused_starts_again() -> None:
    renders = Renders()
    renders.at(loop(deps=(1,)), 0)
    renders.at(loop(deps=(1,), is_playing=False), 0.25)
    renders.at(loop(deps=(2,), is_playing=False), 0.5)
    renders.at(loop(deps=(1,), is_playing=False), 0.75)

    assert renders.at(loop(deps=(1,)), 1.5) == "0"


@pytest.mark.parametrize("period", [timedelta(), timedelta(seconds=-1)], ids=["zero", "negative"])
def test_a_loop_without_a_positive_period_raises(period: timedelta) -> None:
    @component
    def looping() -> Text:
        return Text(content=f"{use_loop(period)}")

    with pytest.raises(ValueError, match="positive period"):
        Renders().at(Div(children=(looping(),)), 0)
